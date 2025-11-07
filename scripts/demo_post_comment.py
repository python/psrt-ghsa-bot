#!/usr/bin/env python3
"""Demo script for posting a comment to a GitHub Security Advisory.

This script demonstrates how to use the post_ghsa_comment function to add
a comment to a GHSA using Playwright automation.

Usage:
    python scripts/demo_post_comment.py
    python scripts/demo_post_comment.py --debug
    python scripts/demo_post_comment.py --ghsa GHSA-xxxx-xxxx-xxxx --comment "My comment text"
"""

import argparse
import sys
from datetime import datetime

from psrt_ghsa_bot.polyfills import GitHubPlaywrightClient, post_ghsa_comment


def main() -> None:
    """Run the demo."""
    parser = argparse.ArgumentParser(description="Post a comment to a GHSA")
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
    parser.add_argument(
        "--comment",
        default=None,
        help="Comment text to post (default: auto-generated timestamp comment)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode (visible browser, slow motion)",
    )

    args = parser.parse_args()

    owner = args.owner
    repo = args.repo
    ghsa_id = args.ghsa

    # Generate a default comment with timestamp if not provided
    if args.comment:
        comment_text = args.comment
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        comment_text = f"Test comment posted by demo script at {timestamp}"

    print(f"📝 Posting comment to {owner}/{repo}/{ghsa_id}\n")
    print(f"Comment text: {comment_text}\n")

    if args.debug:
        print("🐛 Debug mode: Browser window visible, slow motion enabled\n")

    # Initialize Playwright client
    with GitHubPlaywrightClient(
        headless=not args.debug,
        slow_mo=1000 if args.debug else 0,
    ) as client:
        # Authenticate
        print("🔐 Authenticating...")
        try:
            client.authenticate()
        except RuntimeError as e:
            print(f"\n❌ Authentication failed: {e}")
            print("\nPlease ensure you have set up authentication:")
            print("  1. Set GH_BOT_USERNAME and GH_BOT_PASSWORD in .env")
            print("  2. Or run scripts/setup_auth.py for manual login")
            sys.exit(1)

        # Post the comment
        print("📤 Posting comment to GHSA...")
        try:
            comment_id = post_ghsa_comment(client, owner, repo, ghsa_id, comment_text)

            print("\n✅ Comment posted successfully!")
            print(f"   Comment ID: {comment_id}")
            print(f"   View at: https://github.com/{owner}/{repo}/security/advisories/{ghsa_id}")

        except Exception as e:
            print(f"\n❌ Failed to post comment: {e}")
            sys.exit(1)

    print("\n✅ Demo complete!")


if __name__ == "__main__":
    main()
