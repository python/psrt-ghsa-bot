import json
from unittest import mock

from codeowners import CodeOwners

from psrt_ghsa_bot import _codeowners


def _request_failed(status_code: int) -> _codeowners.RequestFailed:
    """Build a githubkit RequestFailed exception w/ the given status code."""
    response = mock.Mock()
    response.status_code = status_code
    return _codeowners.RequestFailed(response)


def test_code_owners_for_files() -> None:
    code_owners = CodeOwners("""
*.py @StanFromIreland
Doc/ @python/docs
""")

    users, teams = _codeowners.code_owners_for_files(code_owners, ["x.py", "Doc/index.rst", "README.md"])
    assert users == {"stanfromireland"}
    assert teams == {"python/docs"}

    users, teams = _codeowners.code_owners_for_files(code_owners, ["Modules/spam.c"])
    assert users == set()
    assert teams == set()


def test_load_codeowners() -> None:
    github = mock.Mock()
    response = mock.Mock()
    response.content = b"*.py @StanFromIreland\n"
    github.rest.repos.get_content.return_value = response

    # CODEOWNERS are available
    code_owners = _codeowners.load_codeowners(github, "owner", "repo")
    github.rest.repos.get_content.assert_called_once_with(
        owner="owner",
        repo="repo",
        path=".github/CODEOWNERS",
        ref="main",
        headers={"Accept": "application/vnd.github.raw+json"},
    )
    assert code_owners.of("x.py") == [("USERNAME", "@StanFromIreland")]

    # CODEOWNERS are missing
    github.rest.repos.get_content.side_effect = _request_failed(404)
    assert _codeowners.load_codeowners(github, "owner", "repo") is None


def test_get_advisory_changed_files() -> None:
    github = mock.Mock()
    pulls_response = mock.Mock()
    pulls_response.content = json.dumps([{"number": 7}]).encode()
    github.rest.pulls.list.return_value = pulls_response
    files_response = mock.Mock()
    files_response.content = json.dumps([{"filename": "Lib/foo.py"}, {"filename": "Doc/bar.rst"}]).encode()
    github.rest.pulls.list_files.return_value = files_response

    private_fork = {"owner": {"login": "fork-owner"}, "name": "fork"}
    files = _codeowners.get_advisory_changed_files(github, private_fork)

    # Only open PRs against the 'main' branch are considered
    github.rest.pulls.list.assert_called_once_with(
        owner="fork-owner", repo="fork", state="open", base="main", per_page=100
    )
    github.rest.pulls.list_files.assert_called_once_with(owner="fork-owner", repo="fork", pull_number=7, per_page=100)
    assert files == {"Doc/bar.rst", "Lib/foo.py"}


def test_get_advisory_changed_files_no_open_pr() -> None:
    github = mock.Mock()
    pulls_response = mock.Mock()
    pulls_response.content = json.dumps([]).encode()
    github.rest.pulls.list.return_value = pulls_response

    files = _codeowners.get_advisory_changed_files(github, {"owner": {"login": "fork-owner"}, "name": "fork"})
    assert files == set()
    github.rest.pulls.list_files.assert_not_called()

    github.rest.pulls.list.side_effect = _request_failed(404)
    files = _codeowners.get_advisory_changed_files(github, {"owner": {"login": "fork-owner"}, "name": "fork"})
    assert files == set()
