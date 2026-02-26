"""Entry point for the gh-issues-tui application.

Modes
-----
Issue list (default):
    dion-issues --repo OWNER/REPO

Combined issues + PR feed (one or more repos):
    dion-issues --feed --repo OWNER/REPO [--repo OWNER2/REPO2] ...
    dion-issues --feed --repo OWNER/REPO --label bug --kind pr
    dion-issues --feed --repo OWNER/REPO --author octocat
    dion-issues --feed --repo OWNER/REPO --refresh-interval 30

Notifications:
    dion-issues --notif
    dion-issues --notif --all
    dion-issues --notif --repo OWNER/REPO
    dion-issues --notif --kind PullRequest
    dion-issues --notif --reason mention
    dion-issues --notif --refresh-interval 60

Environment variables override defaults; flags override env vars.
"""

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dion-issues",
        description="Keyboard-driven terminal UI for GitHub Issues, PRs, and Notifications.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # --- Mode ---
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--feed",
        action="store_true",
        help="Show combined issues + pull request feed.",
    )
    mode_group.add_argument(
        "--notif",
        action="store_true",
        help="Show GitHub notifications.",
    )

    # --- Repo targeting (accepts multiple for feed) ---
    parser.add_argument(
        "--repo",
        metavar="OWNER/REPO",
        action="append",
        dest="repos",
        help="Target repository. Repeat for multiple repos (feed mode). "
             "Defaults to $DION_ISSUES_REPO.",
    )

    # --- Feed / notification filters ---
    parser.add_argument(
        "--label",
        metavar="NAME",
        default=None,
        help="Filter by label name (substring, case-insensitive). Feed mode only.",
    )
    parser.add_argument(
        "--author",
        metavar="LOGIN",
        default=None,
        help="Filter by author login (substring, case-insensitive). Feed mode only.",
    )
    parser.add_argument(
        "--kind",
        metavar="TYPE",
        default=None,
        help=(
            "Feed mode: 'issue' or 'pr'. "
            "Notif mode: 'Issue', 'PullRequest', 'Commit', 'Release', 'Discussion'."
        ),
    )
    parser.add_argument(
        "--reason",
        metavar="REASON",
        default=None,
        help="Notifications only. Filter by reason: mention, assign, review_requested, …",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_notifs",
        help="Notifications only. Show read and unread (default: unread only).",
    )
    parser.add_argument(
        "--refresh-interval",
        metavar="SECONDS",
        type=int,
        default=None,
        help="Auto-refresh interval in seconds. Default: 60 (feed), 120 (notif).",
    )

    args = parser.parse_args()

    # --- Resolve repos ---
    env_repo = os.environ.get("DION_ISSUES_REPO")
    repos: list[str] = args.repos or ([env_repo] if env_repo else [])

    if args.notif:
        # Notifications mode: repos are optional filters; no repo required.
        _validate_repos(parser, repos, required=False)
        _run_notif(args, repos)
    elif args.feed:
        # Feed mode: at least one repo required.
        _validate_repos(parser, repos, required=True)
        _run_feed(args, repos)
    else:
        # Default issue-list mode: exactly one repo required.
        _validate_repos(parser, repos, required=True)
        if len(repos) > 1:
            parser.error(
                "Issue list mode accepts only one --repo. "
                "Use --feed for multiple repos."
            )
        repo = repos[0]
        from gh_issues.ui.app import run
        run(repo)


def _run_feed(args: argparse.Namespace, repos: list[str]) -> None:
    from gh_issues.ui.app import run_feed
    run_feed(
        repos=repos,
        refresh_interval=args.refresh_interval or 60,
        preset_label=args.label,
        preset_author=args.author,
        preset_kind=args.kind,
    )


def _run_notif(args: argparse.Namespace, repos: list[str]) -> None:
    from gh_issues.ui.app import run_notif
    run_notif(
        filter_repos=repos or None,
        filter_kind=args.kind,
        filter_reason=args.reason,
        all_notifs=args.all_notifs,
        refresh_interval=args.refresh_interval or 120,
    )


def _validate_repos(
    parser: argparse.ArgumentParser,
    repos: list[str],
    required: bool,
) -> None:
    if required and not repos:
        parser.error(
            "No repository specified.\n"
            "Use --repo OWNER/REPO or set the DION_ISSUES_REPO environment variable."
        )
    for repo in repos:
        if repo.count("/") != 1:
            parser.error(
                f"Invalid repository format '{repo}'. Expected 'OWNER/REPO'."
            )


if __name__ == "__main__":
    main()
