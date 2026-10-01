#!/usr/bin/env python3
"""Verify a pull request's changed files against Guard, and gate the merge on the result.

The CI sibling of ``guard_hook.py``. The hook verifies ONE write as an agent makes it;
this verifies a whole diff after the fact, so the same engine covers agents that never
touch a Claude Code session -- a teammate's Cursor, an autonomous PR bot, a human.

    guard-ci review --base <sha> --head <sha> --repo <slug> [--env PRODUCTION]

What it is, and is not
----------------------
This is the **interim v1 gate**: it blocks on structural and policy findings -- a
hallucinated import, destructive SQL, ``eval()``, a hardcoded credential -- and reports
blast radius as advisory. That split is a measurement, not a preference. On a 20-file
Django PR, 100% of files escalated on DEGRADED confidence alone, because resolving the
rest of the graph needs type inference Guard does not have. A gate that escalates every
PR carries no information and gets switched off, so the half that works ships now and the
other half rides along as advice until resolution improves.

Advisory mode is a SERVER setting (``NUCLEUS_IMPACT_BLAST_RADIUS_ADVISORY``), deliberately
not a flag here. A client that could ask for leniency is a client that will be asked to.

Whole files, not patches
------------------------
Guard verifies the post-image of each changed file, not the diff hunk. It reasons about
the file that will exist after the merge -- which is the thing that either has a
hallucinated import in it or does not. A hunk alone cannot answer that.

Exit codes
----------
``0`` GREEN, ``1`` RED or YELLOW, ``2`` the run itself failed. Anything non-zero blocks
the merge, and a failure to verify blocks too: an unverified change is not a safe change.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TIMEOUT_SECONDS = 120
INDEX_TIMEOUT_SECONDS = 900

EXIT_GREEN = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2

# Worst-wins, and the ordering is the product's, not this file's: RED blocks, YELLOW
# blocks AND raises an escalation, GREEN merges.
_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}

_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".sql": "sql",
}


@dataclass
class FileVerdict:
    """One changed file's outcome."""

    path: str
    change: str
    status: str
    reason: str = ""
    escalation_id: str | None = None
    verdict_id: str | None = None
    blocking: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    approved_by: str | None = None
    approved_at: str | None = None
    grant_id: str | None = None


def run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return its stdout.

    Args:
        args: Arguments after ``git``.
        cwd: Repository working directory.

    Returns:
        Decoded stdout, stripped.

    Raises:
        RuntimeError: If git fails. The caller turns this into a BLOCKED run rather than
            an allowed one -- a diff we cannot read is a diff we cannot verify.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def changed_files(base: str, head: str, cwd: str) -> list[tuple[str, str]]:
    """Enumerate what the PR changes.

    Uses ``base...head`` (three dots): the changes on the PR's side of the merge base,
    which is what review is about. Two dots would also report everything that landed on
    the base branch since the PR forked, and blame the PR author for it.

    Args:
        base: Base commit or ref.
        head: Head commit or ref.
        cwd: Repository working directory.

    Returns:
        ``(status, path)`` pairs. Status is git's letter: A, M, D, R###, C###.
    """
    raw = run_git(["diff", "--name-status", f"{base}...{head}"], cwd)
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0].strip()
        # A rename is `R100\told\tnew`. The NEW path is what will exist after the merge.
        path = parts[-1].strip()
        out.append((status, path))
    return out


def file_at(commit: str, path: str, cwd: str) -> str | None:
    """Read a file's content at a commit.

    Args:
        commit: The commit to read from.
        path: Repo-relative path.
        cwd: Repository working directory.

    Returns:
        The content, or None when the blob cannot be read as text (binary, or absent).
    """
    try:
        return run_git(["show", f"{commit}:{path}"], cwd)
    except RuntimeError:
        return None


def language_of(path: str) -> str:
    """Map a path to the language Guard should parse it as.

    Args:
        path: Repo-relative path.

    Returns:
        The language name, or ``unknown`` -- which Guard treats as a refusal to analyse
        rather than as a clean result.
    """
    for suffix, language in _LANGUAGE_BY_SUFFIX.items():
        if path.endswith(suffix):
            return language
    return "unknown"


def build_request(
    *,
    repo: str,
    path: str,
    content: str,
    commit: str,
    environment: str,
    author: str,
    organization: str,
    session_id: str,
) -> dict[str, Any]:
    """Build one verification request.

    The envelope mirrors ``guard_hook.py`` deliberately -- same shape, same pinned
    ``action_type``, so a CI verdict and a hook verdict are the same kind of record and
    land in the audit trail identically.

    ``action_type`` is pinned to CODE_CHANGE here exactly as it is in the hook: a caller
    that could name its own action type could name a harmless one.

    Args:
        repo: The registered repository slug.
        path: Repo-relative path of the changed file.
        content: The file's FULL content at head.
        commit: The head commit, which binds the fingerprint to reviewed bytes.
        environment: Target environment for the merge.
        author: The PR author, recorded as the accountable human.
        organization: The organization the author belongs to.
        session_id: One id for the whole PR, so its files group in the audit trail.

    Returns:
        The request body.
    """
    user = {"user_id": author, "organization_id": organization, "roles": []}
    agent = {
        "agent_id": "github-actions",
        "agent_type": "CODING_ASSISTANT",
        "model_provider": "ANTHROPIC",
        "model_name": "unknown",
    }
    return {
        "session_context": {
            "session_id": session_id,
            "user_context": user,
            "agents_involved": [agent],
            "workspace_id": repo,
        },
        "agent_context": agent,
        "user_context": user,
        "action_metadata": {
            "action_id": str(uuid.uuid4()),
            "action_type": "CODE_CHANGE",
            "target_environment": environment,
            "target_system": repo,
            "payload": {
                "content": content,
                "path": path,
                "language": language_of(path),
                "commit_sha": commit,
            },
        },
    }


def ensure_index_at_head(
    *, repo: str, head: str, cwd: str, guard_url: str, token: str
) -> dict[str, Any]:
    """Make sure Guard's index describes the commit being reviewed.

    This is not an optimisation, it is a correctness prerequisite. Guard's existence check
    compares a proposed change against the symbols it holds; if those were built at a
    different commit, a function added on this branch reads as missing and a function
    deleted on it reads as present. So Guard escalates every mutating action against a
    stale index -- correctly, and uselessly, because in CI the index never matches a PR
    head by chance. Measured: every file of a 3-file demo diff escalated on staleness
    alone, saying nothing about the diff.

    The runner already has the worktree checked out at head, so it sends that. `git
    archive` is used rather than tarring the working directory: it writes exactly the tree
    at that commit, excludes `.git`, and cannot pick up untracked scratch files that were
    never part of the change.

    Idempotent by SHA, so calling it before every review is free after the first job.

    Args:
        repo: The registered repository slug.
        head: The head commit.
        cwd: Repository working directory.
        guard_url: Guard's base URL.
        token: The CI bearer credential.

    Returns:
        Guard's response: ``{"indexed": bool, ...}``.

    Raises:
        RuntimeError: If the archive could not be built or Guard refused it. The caller
            BLOCKS -- reviewing against an index we could not place is exactly the
            comparison this function exists to prevent.
    """
    try:
        archive = subprocess.run(
            ["git", "archive", "--format=tar.gz", head],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"could not run git archive: {exc}") from exc

    if archive.returncode != 0:
        detail = archive.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git archive {head} failed: {detail}")

    boundary = f"----guardci{uuid.uuid4().hex}"
    body = _multipart(boundary, {"commit_sha": head}, ("archive", "repo.tar.gz", archive.stdout))

    request = urllib.request.Request(
        f"{guard_url.rstrip('/')}/v1/repositories/{repo}/index",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=INDEX_TIMEOUT_SECONDS) as response:
            parsed: dict[str, Any] = json.loads(response.read())
            return parsed
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("message", str(exc))
        except (ValueError, OSError):
            detail = str(exc)
        raise RuntimeError(f"Guard refused the index upload: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Guard is unreachable: {exc}") from exc


def _multipart(
    boundary: str, fields: dict[str, str], file_field: tuple[str, str, bytes]
) -> bytes:
    """Encode one multipart/form-data body.

    Hand-rolled because this script has no dependencies beyond the standard library, the
    same constraint ``guard_hook.py`` runs under -- a CI gate that needs ``pip install``
    before it can refuse a bad merge is a gate that will be skipped.

    Args:
        boundary: The multipart boundary.
        fields: Plain text fields.
        file_field: ``(name, filename, content)``.

    Returns:
        The encoded body.
    """
    crlf = "\r\n"
    parts: list[bytes] = []

    for name, value in fields.items():
        header = f'--{boundary}{crlf}Content-Disposition: form-data; name="{name}"{crlf}{crlf}'
        parts.append(header.encode("utf-8"))
        parts.append(f"{value}{crlf}".encode())

    name, filename, content = file_field
    header = (
        f"--{boundary}{crlf}"
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"{crlf}'
        f"Content-Type: application/gzip{crlf}{crlf}"
    )
    parts.append(header.encode("utf-8"))
    parts.append(content)
    parts.append(f"{crlf}--{boundary}--{crlf}".encode())

    return b"".join(parts)

def verify(payload: dict[str, Any], guard_url: str, token: str) -> dict[str, Any]:
    """Submit one file for verification.

    Args:
        payload: The request body.
        guard_url: Guard's base URL.
        token: The CI bearer credential.

    Returns:
        Guard's response body.

    Raises:
        RuntimeError: If Guard could not be reached or refused to answer. The caller
            BLOCKS -- Guard being unreachable is not Guard saying yes.
    """
    request = urllib.request.Request(
        f"{guard_url.rstrip('/')}/v1/verify",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body: dict[str, Any] = json.loads(response.read())
            return body
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("message", str(exc))
        except (ValueError, OSError):
            detail = str(exc)
        raise RuntimeError(f"Guard returned an error: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Guard is unreachable: {exc}") from exc


def _messages(reasons: list[dict[str, Any]] | None) -> list[str]:
    """Flatten a verdict's reason blocks into plain lines.

    Args:
        reasons: Blocking or escalating reason objects.

    Returns:
        Every message, in order.
    """
    return [m for block in (reasons or []) for m in block.get("messages", [])]


def review_file(
    status: str,
    path: str,
    *,
    head: str,
    cwd: str,
    repo: str,
    environment: str,
    author: str,
    organization: str,
    session_id: str,
    guard_url: str,
    token: str,
) -> FileVerdict:
    """Verify one changed file.

    Deletions and renames get a YELLOW without calling Guard, and that is the honest
    answer rather than a shortcut. Guard verifies the post-image of a file; a deletion has
    no post-image, so there is nothing to submit. Deleting a widely-depended-on module is
    exactly the blast-radius case the product exists for, and until deletion analysis
    lands the only truthful outcome is "a human must look" -- never a silent GREEN.

    Args:
        status: Git's status letter for this file.
        path: Repo-relative path (the NEW path for a rename).
        head: Head commit. Only the head image is verified -- Guard reasons about the
            file that will exist after the merge, not about the diff hunk.
        cwd: Repository working directory.
        repo: Registered repository slug.
        environment: Target environment.
        author: PR author.
        organization: Author's organization.
        session_id: Shared session id for this PR.
        guard_url: Guard's base URL.
        token: CI bearer credential.

    Returns:
        This file's verdict.
    """
    letter = status[0]

    if letter == "D":
        return FileVerdict(
            path=path,
            change="deleted",
            status="YELLOW",
            reason=(
                "This file is deleted, so there is no content to verify. Guard cannot "
                "measure what a deletion breaks yet, and a deletion of something widely "
                "depended on is precisely the case worth checking. A human must look."
            ),
        )

    content = file_at(head, path, cwd)
    if content is None:
        return FileVerdict(
            path=path,
            change="unreadable",
            status="YELLOW",
            reason=(
                "Guard could not read this file at the head commit -- it may be binary, "
                "or removed by a later commit. An unverified change is not a safe change."
            ),
        )

    # `status`, not `letter`: git writes a rename as `R100`, and `status[0]` is just "R".
    # A rename WITH edits (R097 and friends) has a real post-image and is verified below;
    # only the content-identical case takes this branch.
    if status == "R100":
        return FileVerdict(
            path=path,
            change="renamed",
            status="YELLOW",
            reason=(
                "This file was renamed without edits. Its content is unchanged, but every "
                "importer of the old path now refers to a module that is not there, and "
                "Guard cannot see that from the moved file alone. A human must look."
            ),
        )

    body = build_request(
        repo=repo,
        path=path,
        content=content,
        commit=head,
        environment=environment,
        author=author,
        organization=organization,
        session_id=session_id,
    )
    response = verify(body, guard_url, token)
    verdict = response.get("verdict") or {}

    return FileVerdict(
        path=path,
        change={"A": "added", "M": "modified"}.get(letter, letter.lower()),
        status=str(verdict.get("status", "RED")),
        reason=str(verdict.get("reason", "")),
        escalation_id=response.get("escalation_id"),
        verdict_id=verdict.get("verdict_id"),
        blocking=_messages(verdict.get("blocking_reasons")),
        advisories=[m for a in (verdict.get("advisories") or []) for m in a.get("messages", [])],
    )


def redeem_approval(escalation_id: str, guard_url: str, token: str) -> dict[str, Any]:
    """Ask Guard whether this exact change has already been approved, and spend it.

    Guard reads the fingerprint it stored on this escalation and looks for a grant bound
    to it. The fingerprint is never named here -- a caller that could name it would be
    asserting the identity its own approval is checked against.

    Args:
        escalation_id: The escalation raised by THIS verification.
        guard_url: Guard's base URL.
        token: The CI bearer credential.

    Returns:
        ``{"redeemed": bool, ...}``. A non-redeemable change simply stays escalated; the
        response deliberately does not say whether that is because nobody approved it,
        because the grant was already spent, or because it expired.

    Raises:
        RuntimeError: If Guard could not be reached or refused the request.
    """
    request = urllib.request.Request(
        f"{guard_url.rstrip('/')}/v1/grants/redeem",
        data=json.dumps({"escalation_id": escalation_id}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body: dict[str, Any] = json.loads(response.read())
            return body
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("message", str(exc))
        except (ValueError, OSError):
            detail = str(exc)
        raise RuntimeError(f"Guard refused the approval check: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Guard is unreachable: {exc}") from exc


def apply_approvals(
    verdicts: list[FileVerdict], *, guard_url: str, token: str, enabled: bool
) -> list[FileVerdict]:
    """Let an approval a human already gave unblock the files it covers.

    Without this the loop had no end in CI: a reviewer could approve a finding and the
    check would keep failing forever, because the runner cannot hold the single-use token
    the agent flow uses. The only way forward was to push a change that made the finding
    go away -- which is the reviewer's judgement being overridden by the tooling.

    Only YELLOW files are offered. A RED file is blocked on a positive finding, not parked
    for a decision, and no approval turns one into a pass.

    Args:
        verdicts: This run's per-file verdicts.
        guard_url: Guard's base URL.
        token: The CI bearer credential.
        enabled: False for the manual-token path, where a reviewer hands the grant over
            deliberately and CI must not spend approvals on its own.

    Returns:
        The verdicts, with redeemed files promoted to GREEN and carrying provenance.

    Raises:
        RuntimeError: If Guard could not be reached. Propagated rather than swallowed: a
            run that could not check for approvals has not established that there are
            none, and reporting "still escalated" would be an answer it did not get.
    """
    if not enabled:
        return verdicts

    for verdict in verdicts:
        if verdict.status != "YELLOW" or not verdict.escalation_id:
            continue

        outcome = redeem_approval(verdict.escalation_id, guard_url, token)
        if not outcome.get("redeemed"):
            continue

        verdict.status = "GREEN"
        verdict.approved_by = outcome.get("approved_by")
        verdict.approved_at = outcome.get("approved_at")
        verdict.grant_id = outcome.get("grant_id")
        verdict.reason = (
            f"Approved by {verdict.approved_by} and verified byte-identical to the change "
            "they reviewed. The approval grant is now spent."
        )

    return verdicts


def aggregate(verdicts: list[FileVerdict]) -> str:
    """Combine per-file verdicts into one answer for the PR.

    Worst wins. Not a count, not a ratio: one hallucinated import in one file is a broken
    merge however many other files are clean.

    Args:
        verdicts: Every file's verdict.

    Returns:
        GREEN, YELLOW, or RED. GREEN when there was nothing to review at all -- a PR that
        touches no verifiable file has no finding, and inventing one would train people to
        ignore the gate.
    """
    if not verdicts:
        return "GREEN"
    return max((v.status for v in verdicts), key=lambda s: _RANK.get(s, 2))


def render_markdown(overall: str, verdicts: list[FileVerdict], dashboard: str | None) -> str:
    """Render the PR comment.

    Args:
        overall: The aggregate verdict.
        verdicts: Per-file verdicts.
        dashboard: Base dashboard URL, for escalation links.

    Returns:
        Markdown.
    """
    icon = {"GREEN": "✅", "YELLOW": "⚠️", "RED": "⛔"}.get(overall, "⛔")
    headline = {
        "GREEN": "Devolyn Guard verified this change.",
        "YELLOW": "Devolyn Guard needs a human to look at this change.",
        "RED": "Devolyn Guard blocked this change.",
    }.get(overall, "Devolyn Guard could not verify this change.")

    lines = [f"## {icon} {headline}", ""]

    blocked = [v for v in verdicts if v.status == "RED"]
    escalated = [v for v in verdicts if v.status == "YELLOW"]
    clean = [v for v in verdicts if v.status == "GREEN"]

    if blocked:
        lines += ["### Blocked", ""]
        for v in blocked:
            lines.append(f"**`{v.path}`**")
            lines += [f"- {m}" for m in (v.blocking or [v.reason])]
            lines.append("")

    if escalated:
        lines += ["### Needs review", ""]
        for v in escalated:
            link = ""
            if v.escalation_id and dashboard:
                link = f" — [review it]({dashboard.rstrip('/')}/queue)"
            lines.append(f"**`{v.path}`** ({v.change}){link}")
            lines.append(f"- {v.reason}")
            lines.append("")
        lines += [
            "> Approving in the dashboard mints a single-use grant bound to these exact "
            "bytes at this exact commit. **Push another commit and the approval no longer "
            "applies** — re-run this check without pushing.",
            "",
        ]

    approved = [v for v in clean if v.approved_by]
    if approved:
        lines += ["### Approved", ""]
        for v in approved:
            when = f" on {v.approved_at}" if v.approved_at else ""
            lines.append(
                f"**`{v.path}`** — approved by **{v.approved_by}**{when}, and verified "
                "byte-identical to the change they reviewed."
            )
        lines += [
            "",
            "> The approval grant for each file above is now spent. Pushing another commit "
            "changes what is being reviewed, so it will escalate again.",
            "",
        ]

    plain = [v for v in clean if not v.approved_by]
    if plain:
        lines += [f"<details><summary>{len(plain)} file(s) verified clean</summary>", ""]
        lines += [f"- `{v.path}` ({v.change})" for v in plain]
        lines += ["", "</details>", ""]

    advisories = [(v.path, m) for v in verdicts for m in v.advisories]
    if advisories:
        lines += [
            f"<details><summary>{len(advisories)} advisory note(s) — not blocking</summary>",
            "",
        ]
        lines += [f"- `{p}`: {m}" for p, m in advisories]
        lines += ["", "</details>", ""]

    lines += [
        "",
        "_Blast radius is advisory in this gate: Guard reports what a change may reach "
        "but does not block on it. Structural and policy findings block._",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Review a diff and gate on the result.

    Args:
        argv: Arguments, for tests. Defaults to the real command line.

    Returns:
        0 GREEN, 1 RED/YELLOW, 2 the run itself failed.
    """
    parser = argparse.ArgumentParser(prog="guard-ci")
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="verify a pull request's changed files")
    review.add_argument("--base", required=True, help="base commit or ref")
    review.add_argument("--head", required=True, help="head commit or ref")
    review.add_argument("--repo", required=True, help="registered repository slug")
    review.add_argument("--env", default="PRODUCTION", dest="environment")
    review.add_argument("--author", default="unknown", help="PR author")
    review.add_argument("--organization", default="unknown")
    review.add_argument("--cwd", default=".", help="repository working directory")
    review.add_argument(
        "--manual-grant",
        action="store_true",
        help=(
            "Do not spend approvals automatically. For repositories that want the "
            "stronger property that a human hands the grant over deliberately, at the "
            "cost of pasting a single-use credential into CI."
        ),
    )
    review.add_argument("--json-out", help="write the machine-readable summary here")
    review.add_argument("--markdown-out", help="write the PR comment here")

    args = parser.parse_args(argv)

    # The summary carries non-ASCII (status icons, the em dashes in Guard's own messages),
    # and a Windows console defaults to cp1252, which cannot encode them. Without this the
    # gate crashes AFTER verifying everything -- the worst possible place, because the work
    # is done and the answer is lost. Replace rather than raise: a mangled character is a
    # cosmetic problem, a lost verdict is not.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    guard_url = os.environ.get("NUCLEUS_GUARD_URL", "").strip()
    token = os.environ.get("NUCLEUS_GUARD_TOKEN", "").strip()
    dashboard = os.environ.get("NUCLEUS_GUARD_DASHBOARD_URL", "").strip() or guard_url

    if not guard_url or not token:
        # Misconfiguration BLOCKS, exactly as it does in the hook. A gate that passes when
        # it is not configured protects nothing, in a repo whose owners believe it does.
        print(
            "guard-ci: NUCLEUS_GUARD_URL and NUCLEUS_GUARD_TOKEN must both be set. "
            "Refusing to report a result: an unverified change is not a safe change.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # BEFORE any verification: reviewing against a stale index compares new code with old
    # symbols, which is a correctness problem rather than a caveat, and escalates
    # everything for a reason that says nothing about the diff.
    try:
        placed = ensure_index_at_head(
            repo=args.repo, head=args.head, cwd=args.cwd, guard_url=guard_url, token=token
        )
    except RuntimeError as exc:
        print(f"guard-ci: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if placed.get("indexed"):
        print(
            f"guard-ci: indexed {args.repo} at {args.head[:12]} "
            f"({placed.get('files', '?')} files, {placed.get('elapsed_ms', '?')}ms)",
            file=sys.stderr,
        )
    else:
        print(f"guard-ci: index already current at {args.head[:12]}", file=sys.stderr)

    try:
        files = changed_files(args.base, args.head, args.cwd)
    except RuntimeError as exc:
        print(f"guard-ci: {exc}", file=sys.stderr)
        return EXIT_ERROR

    session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{args.repo}:{args.head}"))

    verdicts: list[FileVerdict] = []
    for status, path in files:
        if language_of(path) == "unknown":
            # Not a language Guard analyses. Skipped rather than reported: a file it was
            # never going to inspect is not a finding, and listing it as one would bury
            # the findings that matter.
            continue
        try:
            verdicts.append(
                review_file(
                    status,
                    path,
                    head=args.head,
                    cwd=args.cwd,
                    repo=args.repo,
                    environment=args.environment,
                    author=args.author,
                    organization=args.organization,
                    session_id=session_id,
                    guard_url=guard_url,
                    token=token,
                )
            )
        except RuntimeError as exc:
            print(f"guard-ci: {path}: {exc}", file=sys.stderr)
            return EXIT_ERROR

    try:
        verdicts = apply_approvals(
            verdicts, guard_url=guard_url, token=token, enabled=not args.manual_grant
        )
    except RuntimeError as exc:
        print(f"guard-ci: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Re-aggregated AFTER approvals, so a PR whose only findings were approved passes.
    overall = aggregate(verdicts)
    markdown = render_markdown(overall, verdicts, dashboard)

    summary = {
        "status": overall,
        "base": args.base,
        "head": args.head,
        "repository": args.repo,
        "files_reviewed": len(verdicts),
        "files": [
            {
                "path": v.path,
                "change": v.change,
                "status": v.status,
                "reason": v.reason,
                "verdict_id": v.verdict_id,
                "escalation_id": v.escalation_id,
                "blocking": v.blocking,
                "advisories": v.advisories,
                "approved_by": v.approved_by,
                "approved_at": v.approved_at,
                "grant_id": v.grant_id,
            }
            for v in verdicts
        ],
    }

    if args.json_out:
        with Path(args.json_out).open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
    if args.markdown_out:
        with Path(args.markdown_out).open("w", encoding="utf-8") as handle:
            handle.write(markdown)

    print(markdown)
    return EXIT_GREEN if overall == "GREEN" else EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
