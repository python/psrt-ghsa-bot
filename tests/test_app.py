import datetime
from unittest import mock

import pytest

from psrt_ghsa_bot import app


@pytest.fixture
def year() -> str:
    return str(datetime.date.today().year)


@pytest.fixture
def cve_id(year) -> str:
    return f"CVE-{year}-0000"


@pytest.fixture
def cve_reserve_response(cve_id, year):
    # See: https://github.com/CVEProject/cve-services/blob/dev/schemas/cve-id/create-cve-ids-response.json
    return {
        "meta": {"remaining_quota": 1000},
        "cve_ids": [
            {
                "cve_id": cve_id,
                "cve_year": year,
                "owning_cna": "PSF",
                "state": "RESERVED",
                "requested_by": {"cna": "PSF", "user": "cna@python.org"},
                "requested": "2024-01-01T00:00:00Z",
            },
        ],
    }


def _create_advisory_dict(state, cve_id, collaborating_teams, summary=""):
    """Helper to create a security advisory dictionary."""
    return {
        "ghsa_id": "GHSA-xxxx-xxxx-xxxx",
        "state": state,
        "summary": summary,
        "cve_id": cve_id,
        "collaborating_teams": [{"slug": team} for team in collaborating_teams],
        "collaborating_users": [{"login": "octocat", "id": 1, "type": "User"}],
    }


@pytest.mark.parametrize("state", ["draft", "triage"])
def test_adds_psrt_github_team_to_security_advisories(state) -> None:
    security_advisory = _create_advisory_dict(state, "CVE-0000-0000", [])

    github = mock.Mock()
    cve_api = mock.Mock()

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
        owner="owner",
        repo="repo",
        ghsa_id="GHSA-xxxx-xxxx-xxxx",
        data={"collaborating_teams": ["psrt"]},
    )


@pytest.mark.parametrize("state", ["draft", "triage"])
def test_appends_psrt_github_team_to_security_advisories(state) -> None:
    security_advisory = _create_advisory_dict(
        state,
        "CVE-0000-0000",
        ["python/other-team"],
    )

    github = mock.Mock()
    cve_api = mock.Mock()

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
        owner="owner",
        repo="repo",
        ghsa_id="GHSA-xxxx-xxxx-xxxx",
        data={"collaborating_teams": ["psrt", "python/other-team"]},
    )


@pytest.mark.parametrize("state", ["closed", "published"])
def test_does_not_modify_completed_security_advisories(state) -> None:
    security_advisory = _create_advisory_dict(state, None, [])

    github = mock.Mock()
    cve_api = mock.Mock()

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    github.rest.security_advisories.update_repository_advisory.assert_not_called()


def test_reserves_cve_id_for_draft_security_advisories(
    year,
    cve_id,
    cve_reserve_response,
) -> None:
    security_advisory = _create_advisory_dict("draft", None, ["psrt"])

    github = mock.Mock()
    cve_api = mock.Mock()
    cve_api.reserve.return_value = cve_reserve_response

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    cve_api.reserve.assert_called_with(count=1, year=year, random=True)
    github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
        owner="owner",
        repo="repo",
        ghsa_id="GHSA-xxxx-xxxx-xxxx",
        data={"cve_id": cve_id},
    )


@pytest.mark.parametrize("state", ["triage", "closed", "published"])
def test_does_not_reserve_cve_id_for_triage_security_advisories(state) -> None:
    security_advisory = _create_advisory_dict(state, None, [])

    github = mock.Mock()
    cve_api = mock.Mock()

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    cve_api.reserve.assert_not_called()
    # Triage state should still add team
    if state == "triage":
        github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
            owner="owner",
            repo="repo",
            ghsa_id="GHSA-xxxx-xxxx-xxxx",
            data={"collaborating_teams": ["psrt"]},
        )
    else:
        github.rest.security_advisories.update_repository_advisory.assert_not_called()


def test_update_collaborating_users() -> None:
    security_advisory = _create_advisory_dict("draft", None, ["psrt"])

    github = mock.Mock()
    cve_api = mock.Mock()

    with (
        mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs,
    ):
        security_advisory = _create_advisory_dict("draft", "CVE-2026-0001", ["psrt"])
        get_repo_advs.return_value = [security_advisory]

        # 'alice' isn't in the GitHub Team, but is in the Devguide list.
        app.apply_to_repo(github, "owner", "repo", cve_api, collaborating_users={"alice"})

    github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
        owner="owner",
        repo="repo",
        ghsa_id="GHSA-xxxx-xxxx-xxxx",
        data={"collaborating_users": ["alice", "octocat"]},
    )


@pytest.mark.parametrize(
    "summary",
    [
        "[CLOSE] perl is better than Python",
        "[CLOSED] 0.1 + 0.2 is broken?!?!?!?!?!",
        "[COMPLETE] some boring security thing",
        "fix soemthing in datetime module [COMPLETED]",
        "blah blah [closed] lowercase blah",
    ],
)
def test_closes_advisory_with_close_or_complete_tag(summary) -> None:
    security_advisory = _create_advisory_dict("triage", None, [], summary=summary)

    github = mock.Mock()
    cve_api = mock.Mock()

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
        owner="owner",
        repo="repo",
        ghsa_id="GHSA-xxxx-xxxx-xxxx",
        data={"state": "closed"},
    )


def test_load_psrt_members_from_devguide() -> None:
    with mock.patch("psrt_ghsa_bot.app.urllib3.request") as urllib3_request:
        resp = mock.Mock()
        resp.status = 200
        resp.data = b"""Barry Warsaw,warsaw,Admin
Benjamin Peterson,benjaminp,
Donald Stufft,dstufft,
Dustin Ingram,di,
Ee Durbin,ewdurbin,Admin
Glyph Lefkowitz,glyph,
Gregory P. Smith,gpshead,"""

        urllib3_request.return_value = resp

        members = app.load_psrt_members_from_devguide()

    assert members == {"warsaw", "benjaminp", "dstufft", "di", "ewdurbin", "glyph", "gpshead"}


def test_reserve_one_cve_id(cve_reserve_response, cve_id, year) -> None:
    cve_api = mock.Mock()
    cve_api.reserve.return_value = cve_reserve_response

    assert app.reserve_one_cve(cve_api) == cve_id

    cve_api.reserve.assert_called_with(count=1, year=year, random=True)
