"""Comment processing service for PSRT GHSA Bot."""

import base64
import contextlib
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from githubkit import AppAuthStrategy, GitHub

from psrt_ghsa_bot.app import get_repository_advisories
from psrt_ghsa_bot.commands.executor import execute_command
from psrt_ghsa_bot.commands.parser import parse_command
from psrt_ghsa_bot.polyfills.comments import get_ghsa_comments, post_ghsa_comment
from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient
from psrt_ghsa_bot.state import StateManager

load_dotenv()


@dataclass
class CommentProcessingStats:
    """Statistics for a comment processing run."""

    ghsas_checked: int = 0
    comments_found: int = 0
    commands_found: int = 0
    commands_executed: int = 0
    commands_skipped: int = 0
    errors: int = 0


def process_ghsa_comments(
        github: GitHub,
        playwright_client: GitHubPlaywrightClient,
        state_manager: StateManager,
        owner: str,
        repo: str,
        ghsa_id: str,
) -> int:
    """Process comments for a single GHSA.

    Args:
        github: Authenticated GitHub API client
        playwright_client: Playwright client for UI automation
        state_manager: State manager for tracking processed commands
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        Number of commands executed
    """
    ghsa_key = f"{owner}/{repo}/{ghsa_id}"

    try:
        comments = get_ghsa_comments(playwright_client, owner, repo, ghsa_id, debug=True)
    except Exception as e:
        print(f"\n         ⚠️  Could not fetch comments: {e}")
        return 0

    if not comments:
        print("\n         💬 No comments found on this GHSA")
        return 0

    print(f"\n         💬 Found {len(comments)} comment(s)")
    commands_executed = 0
    for comment in comments:
        comment_id = comment.id
        author = comment.author
        body = comment.body
        cmd = parse_command(body, author, comment_id, playwright_client.username, comment.created_at)

        if cmd is None:
            body_preview = body[:50].replace('\n', ' ') if body else "(empty)"
            print(f"         ⏩ @{author}: no command | body: {body_preview}... | looking for: @{playwright_client.username}")
            continue

        if state_manager.is_command_processed(ghsa_key, comment_id, body, author):
            print(f"         ⏩ Command from @{author} already processed: {cmd.action}")
            continue

        print(f"\n         🎯 New command from @{author}: @{playwright_client.username} {cmd.action}")
        try:
            result = execute_command(cmd, github, playwright_client, owner, repo, ghsa_id)
            post_ghsa_comment(playwright_client, owner, repo, ghsa_id, result.message)
            state_manager.mark_command_processed(ghsa_key, comment_id, body, author)
            commands_executed += 1
            print(f"         ✅ Command executed successfully")
        except Exception as e:
            print(f"         ❌ Command failed: {e}")
            error_message = (
                f"❌ **Command Execution Failed**\n\n"
                f"@{author}, an error occurred while processing your command:\n\n"
                f"```\n{e!s}\n```\n\n"
                f"Please contact the PSRT team if this error persists."
            )

            with contextlib.suppress(Exception):
                post_ghsa_comment(playwright_client, owner, repo, ghsa_id, error_message)

    return commands_executed


def process_all_comments(
        github: GitHub,
        playwright_client: GitHubPlaywrightClient,
        state_manager: StateManager,
) -> CommentProcessingStats:
    """Process comments for all GHSAs across all installations.

    Args:
        github: Authenticated GitHub API client (app-level)
        playwright_client: Playwright client for UI automation
        state_manager: State manager for tracking processed commands

    Returns:
        CommentProcessingStats with run statistics
    """
    stats = CommentProcessingStats()
    installations = github.rest.paginate(github.rest.apps.list_installations)

    for installation_data in installations:
        print(f"\n📦 Installation: {installation_data.account.login}")
        installation_github = github.with_auth(github.auth.as_installation(installation_data.id))
        repos = installation_github.rest.paginate(
            installation_github.rest.apps.list_repos_accessible_to_installation,
            map_func=lambda r: r.parsed_data.repositories,
        )

        for repo in repos:
            owner = repo.owner.login
            repo_name = repo.name

            try:
                advisories = list(get_repository_advisories(installation_github, owner, repo_name))
                if not advisories:
                    continue

                count = len(advisories)
                print(f"   📂 {owner}/{repo_name}: {count} {'advisory' if count == 1 else 'advisories'}")

                for advisory in advisories:
                    ghsa_id = advisory["ghsa_id"]
                    state_str = advisory["state"]

                    if state_str not in ("triage", "draft"):
                        continue

                    stats.ghsas_checked += 1
                    print(f"      🔍 Checking {ghsa_id} ({state_str})...", end=" ")
                    try:
                        commands_executed = process_ghsa_comments(
                            installation_github,
                            playwright_client,
                            state_manager,
                            owner,
                            repo_name,
                            ghsa_id,
                        )
                        if commands_executed > 0:
                            print(f"✅ {commands_executed} command(s) executed")
                        else:
                            print("⏭️  No new commands")
                        stats.commands_executed += commands_executed
                    except Exception as e:
                        print(f"❌ Error: {e}")
                        stats.errors += 1

            except Exception as e:
                print(f"   ⚠️  Error accessing {owner}/{repo_name}: {e}")
                stats.errors += 1

    return stats


def main() -> None:
    """Cmment processing machine."""
    print("🤖 PSRT GHSA Bot - Comment Processor")
    print("=" * 50)

    print("\n📡 Initializing GitHub API client...")
    gh_client_private_key = base64.b64decode(os.environ["GH_CLIENT_PRIVATE_KEY"]).decode().strip()
    github = GitHub(AppAuthStrategy(os.environ["GH_CLIENT_ID"], gh_client_private_key))

    print("💾 Loading state manager...")
    state_manager = StateManager()
    state_manager.load()

    print("🌐 Starting Playwright browser...")
    with GitHubPlaywrightClient() as playwright_client:
        print("🔐 Authenticating to GitHub...")
        playwright_client.authenticate()
        print("✅ Authentication successful!\n")

        print("🔍 Processing comments across all installations...")
        stats = process_all_comments(github, playwright_client, state_manager)

        print("\n" + "=" * 50)
        print("📊 Processing Summary:")
        print(f"   GHSAs checked: {stats.ghsas_checked}")
        print(f"   Commands executed: {stats.commands_executed}")
        print(f"   Errors: {stats.errors}")
        print("=" * 50)

        print("\n💾 Saving state...")
        state_manager.save()
        print("✅ Done!")


if __name__ == "__main__":
    main()
