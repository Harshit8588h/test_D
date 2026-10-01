#!/usr/bin/env python3
"""Post or update the single Devolyn Guard comment on a pull request.

One comment per PR, edited in place. A gate that appends a new comment on every re-run
buries the conversation it is supposed to inform, and by the third push nobody reads any
of them -- which is the same failure as a gate that escalates everything, arrived at from
a different direction.

The comment is found by a hidden marker rather than by author or position: a marker
survives someone editing the text, GitHub changing how bot comments are attributed, and a
maintainer replying in between. If no marked comment exists, one is created.

Standard library only, like ``guard_ci.py`` and for the same reason: a CI gate that needs
``pip install`` before it can refuse a bad merge is a gate that gets skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

MARKER = "<!-- nucleus-guard-verify -->"
"""Hidden HTML comment identifying our comment. Invisible when rendered."""

TIMEOUT_SECONDS = 30
_API = "https://api.github.com"


def _request(
    url: str, token: str, *, method: str = "GET", body: dict[str, Any] | None = None
) -> Any:
    """Call the GitHub REST API.

    Args:
        url: Absolute URL.
        token: The workflow's GITHUB_TOKEN.
        method: HTTP method.
        body: JSON body, if any.

    Returns:
        The decoded response.

    Raises:
        RuntimeError: On any transport or HTTP error.
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "nucleus-guard-verify-action",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc.code} {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub API is unreachable: {exc}") from exc


def find_existing(comments: list[dict[str, Any]]) -> int | None:
    """Return the id of our comment, if it is already there.

    Args:
        comments: Comment objects from the issues API.

    Returns:
        The comment id, or None.

        Matched on the marker, not on the author. GitHub attributes a workflow comment to
        ``github-actions[bot]`` today, but that is a detail of how the token is minted, and
        a repository using a GitHub App or a PAT attributes it to something else. The
        marker is ours and does not move.
    """
    for comment in comments:
        if MARKER in (comment.get("body") or ""):
            identifier = comment.get("id")
            if isinstance(identifier, int):
                return identifier
    return None


def build_body(summary: str, run_url: str | None = None) -> str:
    """Assemble the comment body.

    Args:
        summary: The markdown the CLI produced.
        run_url: Link back to the workflow run, when known.

    Returns:
        The body, marker first so it survives any later edit of the visible text.
    """
    parts = [MARKER, summary.rstrip()]
    if run_url:
        parts.append(f"\n<sub>[Workflow run]({run_url})</sub>")
    return "\n".join(parts)


def upsert(
    *, repo: str, pr_number: int, token: str, summary: str, run_url: str | None = None
) -> str:
    """Create the comment, or edit the one already there.

    Args:
        repo: ``owner/name``.
        pr_number: The pull request number.
        token: The workflow's GITHUB_TOKEN.
        summary: The markdown the CLI produced.
        run_url: Link back to the workflow run.

    Returns:
        ``"created"`` or ``"updated"``.

    Raises:
        RuntimeError: If the API call fails.
    """
    body = build_body(summary, run_url)

    comments = _request(
        f"{_API}/repos/{repo}/issues/{pr_number}/comments?per_page=100", token
    )
    existing = find_existing(comments or [])

    if existing is None:
        _request(
            f"{_API}/repos/{repo}/issues/{pr_number}/comments",
            token,
            method="POST",
            body={"body": body},
        )
        return "created"

    _request(
        f"{_API}/repos/{repo}/issues/comments/{existing}",
        token,
        method="PATCH",
        body={"body": body},
    )
    return "updated"


def main(argv: list[str] | None = None) -> int:
    """Post or update the PR comment.

    Args:
        argv: Arguments, for tests.

    Returns:
        0 always on the comment step -- the VERDICT decides whether the check passes, and
        it has already been decided by the time this runs. Failing the build because
        GitHub's comment API had a bad minute would turn a reporting problem into a
        blocked merge, and the merge was already correctly blocked or not.
    """
    parser = argparse.ArgumentParser(prog="pr-comment")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--token", required=True)
    parser.add_argument("--summary-file", required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)

    try:
        with open(args.summary_file, encoding="utf-8") as handle:  # noqa: PTH123
            summary = handle.read()
    except OSError as exc:
        print(f"pr-comment: could not read the summary ({exc})", file=sys.stderr)
        return 0

    try:
        action = upsert(
            repo=args.repo,
            pr_number=args.pr,
            token=args.token,
            summary=summary,
            run_url=args.run_url,
        )
    except RuntimeError as exc:
        # Reported, never fatal. See the docstring above.
        print(f"pr-comment: {exc}", file=sys.stderr)
        return 0

    print(f"pr-comment: {action} the Devolyn Guard comment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
