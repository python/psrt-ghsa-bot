#!/usr/bin/env python
"""Demo script for reading GHSA comments using playwright to read comments.

This demonstrates Issue #3 implementation: Reading comments from GitHub
Security Advisories that are not accessible via the GitHub API.

Usage:
    # Headless mode (default)
    uv run python scripts/demo_get_comments.py

    # Debug mode with visible browser (for local development)
    uv run python scripts/demo_get_comments.py --debug

Requirements:
    - Authenticated session (run with --debug for first time manual auth,
      or set GH_BOT_USERNAME/GH_BOT_PASSWORD env vars)


Example:
    ```
    ✗ uv run python scripts/demo_get_comments.py --debug
    🔍 Reading comments from jolt-org/ghsa-testing/GHSA-f3x5-4pp6-r2mf

    🐛 Debug mode: Browser window visible, slow motion enabled

    🔐 Authenticating...
    🔍 Checking saved authentication state...
    ✅ Using saved authentication state
    📥 Fetching comments from GHSA...

    ✅ Found 1 comment(s):

    ================================================================================

    [1] Comment by @JacobCoffee
        ID: comment-0
        Created: 2025-11-05 20:03:21+00:00
        Updated: 2025-11-05 20:03:21+00:00
        Bot: False
        Body:

        test

    --------------------------------------------------------------------------------

    ✅ Demo complete!
    ```
"""

import argparse

from psrt_ghsa_bot.polyfills import GitHubPlaywrightClient, get_ghsa_comments


def main() -> None:
    """Demonstrate reading GHSA comments."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Demo script for reading GHSA comments")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode with visible browser window (headless=False, slow_mo=500)",
    )
    parser.add_argument(
        "--owner",
        default="jolt-org",
        help="Repository owner (default: jolt-org)",
    )
    parser.add_argument(
        "--repo",
        default="ghsa-testing",
        help="Repository name (default: ghsa-testing)",
    )
    parser.add_argument(
        "--ghsa",
        default="GHSA-f3x5-4pp6-r2mf",
        help="GHSA ID (default: GHSA-f3x5-4pp6-r2mf)",
    )
    args = parser.parse_args()

    owner = args.owner
    repo = args.repo
    ghsa_id = args.ghsa

    print(f"🔍 Reading comments from {owner}/{repo}/{ghsa_id}\n")

    # Configure client based on debug mode
    # Create client and authenticate
    if args.debug:
        print("🐛 Debug mode: Browser window visible, slow motion enabled\n")
        client = GitHubPlaywrightClient(headless=False, slow_mo=500)
    else:
        client = GitHubPlaywrightClient(headless=True)

    with client:
        print("🔐 Authenticating...")
        client.authenticate()

        # Get comments
        print("📥 Fetching comments from GHSA...\n")
        comments = get_ghsa_comments(client, owner, repo, ghsa_id)

        # Display results
        if not comments:
            print("ℹ️  No comments found on this GHSA.")
        else:
            print(f"✅ Found {len(comments)} comment(s):\n")
            print("=" * 80)

            for i, comment in enumerate(comments, 1):
                print(f"\n[{i}] Comment by @{comment.author}")
                print(f"    ID: {comment.id}")
                print(f"    Created: {comment.created_at}")
                print(f"    Updated: {comment.updated_at}")
                print(f"    Bot: {comment.is_bot_comment}")
                print("    Body:\n")

                # Indent comment body
                for line in comment.body.split("\n"):
                    print(f"    {line}")

                print("\n" + "-" * 80)

    print("\n✅ Demo complete!")


if __name__ == "__main__":
    main()
