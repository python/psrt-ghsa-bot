"""Resolving CODEOWNERS for the files changed by a GHSA's fix."""

import json
import typing

from codeowners import CodeOwners
from githubkit import GitHub
from githubkit.exception import RequestFailed


def load_codeowners(github: GitHub, owner: str, repo: str) -> CodeOwners | None:
    """Fetch and parse a repo's '.github/CODEOWNERS' on the 'main' branch."""
    try:
        response = github.rest.repos.get_content(
            owner=owner,
            repo=repo,
            path=".github/CODEOWNERS",
            ref="main",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
    except RequestFailed as e:
        if e.response.status_code == 404:
            return None  # No such file
        raise
    return CodeOwners(response.content.decode())


def code_owners_for_files(code_owners: CodeOwners, filenames: typing.Iterable[str]) -> tuple[set[str], set[str]]:
    """Resolve the changed files to the CODEOWNERS (users/teams) for them."""
    users = set()
    teams = set()
    for filename in filenames:
        for kind, owner in code_owners.of(filename):
            if kind == "USERNAME":
                users.add(owner.lstrip("@").lower())
            elif kind == "TEAM":
                teams.add(owner.lstrip("@").lower())
    return users, teams


def get_advisory_changed_files(github: GitHub, private_fork: dict) -> set[str]:
    """List files changed by the open fix pull request (against 'main') in a private fork."""
    try:
        pulls_response = github.rest.pulls.list(
            owner=private_fork["owner"]["login"], repo=private_fork["name"], state="open", base="main", per_page=100
        )
    except RequestFailed as e:
        if e.response.status_code == 404:
            return set()
        raise
    # Parse JSON directly to bypass Pydantic validation
    pulls = json.loads(pulls_response.content)
    if not pulls:
        return set()

    pull = pulls[0]
    files_response = github.rest.pulls.list_files(
        owner=private_fork["owner"]["login"], repo=private_fork["name"], pull_number=pull["number"], per_page=100
    )
    return {file["filename"] for file in json.loads(files_response.content)}
