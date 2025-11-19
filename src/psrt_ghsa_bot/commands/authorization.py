"""Authorization checks for command execution.

Determines if a user is authorized to execute bot commands based on:
- GHSA collaborator status (?)
- Repository admin status
- python/psrt team membership TODO: make this configurable, and allow list of org/teams?
  like, what if we want PSRT to be able to responds across all PSF repos? (psf, python, pycon, pypi?)
  or maybe we just say "team is $TEAM, and this bot works in $ORG as long as you are member of
  that $TEAM" so we leave the user mgmt to the org admins. yeah.. probably that.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from githubkit import GitHub


@dataclass
class AuthorizationResult:
    """Result of authorization check."""

    authorized: bool
    """Whether the user is authorized"""
    reason: str
    """Human-readable reason for the decision"""


def is_authorized(
    github: GitHub,
    username: str,
    owner: str,
    repo: str,
    ghsa_id: str,
) -> AuthorizationResult:
    """Check if user is authorized to execute commands.

    Authorization hierarchy:
    1. Members of python/psrt team
    2. GHSA collaborators
    3. Repository admins

    Args:
        github: Authenticated GitHub client
        username: GitHub username to check
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        AuthorizationResult indicating if user is authorized and a rason
    """
    if _is_psrt_team_member(github, username):
        return AuthorizationResult(
            authorized=True,
            reason=f"User {username} is a member of python/psrt team",
        )

    if _is_ghsa_collaborator(github, username, owner, repo, ghsa_id):
        return AuthorizationResult(
            authorized=True,
            reason=f"User {username} is a collaborator on this advisory",
        )

    if _is_repo_admin(github, username, owner, repo):
        return AuthorizationResult(
            authorized=True,
            reason=f"User {username} is an admin of {owner}/{repo}",
        )

    return AuthorizationResult(
        authorized=False,
        reason=f"User {username} is not authorized to execute commands",
    )


def _is_psrt_team_member(github: GitHub, username: str) -> bool:
    """Check if user is member of python/psrt team.

    Args:
        github: Authenticated GitHub client
        username: GitHub username to check

    Returns:
        True if user is a member of the python/psrt team
    """
    try:
        response = github.rest.teams.get_member_in_org(
            org="python",
            team_slug="psrt",
            username=username,
        )
        return response.status_code == 204
    except Exception:
        return False


def _is_ghsa_collaborator(
    github: GitHub,
    username: str,
    owner: str,
    repo: str,
    ghsa_id: str,
) -> bool:
    """Check if user is collaborator on the GHSA.

    Args:
        github: Authenticated GitHub client
        username: GitHub username to check
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        True if user is a collaborator on the advisory
    """
    try:
        advisory = github.rest.security_advisories.get_repository_advisory(
            owner=owner,
            repo=repo,
            ghsa_id=ghsa_id,
        )

        if not advisory.parsed_data:
            return False

        collaborators = advisory.parsed_data.collaborating_users or []
        teams = advisory.parsed_data.collaborating_teams or []

        for collaborator in collaborators:
            if collaborator.login and collaborator.login.lower() == username.lower():
                return True

        return any(team.slug and _is_team_member(github, owner, team.slug, username) for team in teams)
    except Exception:
        return False


def _is_team_member(
    github: GitHub,
    org: str,
    team_slug: str,
    username: str,
) -> bool:
    """Check if user is member of a specific team.

    Args:
        github: Authenticated GitHub client
        org: Organization name
        team_slug: Team slug
        username: GitHub username to check

    Returns:
        True if user is a member of the team
    """
    try:
        response = github.rest.teams.get_member_in_org(
            org=org,
            team_slug=team_slug,
            username=username,
        )
        return response.status_code == 204
    except Exception:
        return False


def _is_repo_admin(
    github: GitHub,
    username: str,
    owner: str,
    repo: str,
) -> bool:
    """Check if user has admin permissions on repository.

    Args:
        github: Authenticated GitHub client
        username: GitHub username to check
        owner: Repository owner
        repo: Repository name

    Returns:
        True if user is a repository admin
    """
    try:
        response = github.rest.repos.get_collaborator_permission_level(
            owner=owner,
            repo=repo,
            username=username,
        )

        if not response.parsed_data or not response.parsed_data.permission:
            return False

        return response.parsed_data.permission == "admin"
    except Exception:
        return False
