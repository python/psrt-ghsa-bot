import datetime
import itertools
import json
from collections import abc
from unittest import mock

import pytest
import requests
import requests.exceptions as req_exc

from psrt_ghsa_bot import app

PSF_CNA_UUID = "28c92f92-d60d-412d-b760-e73465c3df22"
PSF_CNA_SHORTNAME = "PSF"


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


def cve_isoformat(date_time: datetime.datetime) -> str:
    naive_utc = date_time.astimezone(datetime.UTC).replace(tzinfo=None)
    return f"{naive_utc.isoformat(timespec='milliseconds')}Z"


@pytest.fixture
def show_cve_response(cve_id):
    # See <https://github.com/CVEProject/cve-services/blob/dev/schemas/CVE_JSON_5.2.0_bundled.json>
    # referenced from <https://github.com/CVEProject/cve-services/blob/dev/schemas/cve/get-cve-record-response.json>
    # This is very incomplete for now but can be expanded as we introspect more
    # fields.
    date_updated = datetime.datetime.now(tz=datetime.UTC)
    return {
        "dataType": "CVE_RECORD",
        "dataVersion": "5.2",
        "cveMetadata": {
            "cveId": cve_id,
            "assignerOrgId": PSF_CNA_UUID,
            "state": "PUBLISHED",
            "assignerShortName": PSF_CNA_SHORTNAME,
            "dateReserved": cve_isoformat(date_updated - datetime.timedelta(hours=60)),
            "datePublished": cve_isoformat(date_updated - datetime.timedelta(hours=30)),
            "dateUpdated": cve_isoformat(date_updated),
        },
        "containers": {
            "cna": {
                "credits": [
                    {
                        "lang": "en",
                        "type": "reporter",
                        "value": "User (https://example.com/~user)",
                    },
                    {
                        "lang": "en",
                        "type": "coordinator",
                        "value": "Seth Larson (https://github.com/sethmlarson)",
                    },
                ],
                "providerMetadata": {
                    "orgId": PSF_CNA_UUID,
                    "shortName": PSF_CNA_SHORTNAME,
                    "dateUpdated": cve_isoformat(date_updated),
                },
                "references": [
                    {
                        "tags": ["issue-tracking"],
                        "url": "https://github.com/python/cpython/issues/12345",
                    }
                ],
                "source": {
                    "discovery": "UNKNOWN",
                },
                "title": "Test Vulnerability",
            },
        },
    }


def _build_cve_references(tags: abc.Iterable[str]) -> abc.Iterator[dict]:
    for index, tag in enumerate(tags, 1):
        yield {
            "tags": [tag],
            "url": f"https://example.com/python/{tag}/{index:02d}",
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


def test_does_not_reserve_cve_id_when_reserve_cves_disabled() -> None:
    security_advisory = _create_advisory_dict("draft", None, ["psrt"])

    github = mock.Mock()
    cve_api = mock.Mock()

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api, reserve_cves=False)

    cve_api.reserve.assert_not_called()
    github.rest.security_advisories.update_repository_advisory.assert_not_called()


def test_create_private_fork() -> None:
    github = mock.Mock()
    cve_api = mock.Mock()

    with (
        mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs,
    ):
        security_advisory = _create_advisory_dict("draft", "CVE-2026-0001", ["psrt"])
        security_advisory.pop("private_fork", None)
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    github.rest.security_advisories.create_fork.assert_called_once_with(
        owner="owner",
        repo="repo",
        ghsa_id="GHSA-xxxx-xxxx-xxxx",
    )


def test_get_security_advisory_credits_no_private_fork():
    github = mock.Mock()
    credits = app.get_security_advisory_credits(
        github=github,
        security_advisory={
            "private_fork": None,
        },
    )
    assert credits == []


def test_get_security_advisory_credits_no_prs():
    github = mock.Mock()
    pulls_list = mock.Mock()
    pulls_list.content = "[]"
    github.rest.pulls.list.return_value = pulls_list
    credits = app.get_security_advisory_credits(
        github=github,
        security_advisory={
            "private_fork": {
                "owner": {"login": "fork-owner"},
                "name": "fork-name",
            },
        },
    )
    assert credits == []
    github.rest.pulls.list.assert_called_with(
        owner="fork-owner",
        repo="fork-name",
        state="open",
        per_page=100,
    )


def test_get_security_advisory_credits():
    github = mock.Mock()

    pulls_list = mock.Mock()
    pulls_list.content = json.dumps([{"number": 1, "user": {"login": "author"}}])
    github.rest.pulls.list.return_value = pulls_list

    reviews_list = mock.Mock()
    reviews_list.content = json.dumps([{"user": {"login": "reviewer1"}}, {"user": {"login": "reviewer2"}}])
    github.rest.pulls.list_reviews.return_value = reviews_list

    credits = app.get_security_advisory_credits(
        github=github,
        security_advisory={
            "private_fork": {
                "owner": {"login": "fork-owner"},
                "name": "fork-name",
            },
            "credits": [
                {"type": "coordinator", "login": "reviewer1"},
            ],
        },
    )

    # reviewer1 is kept as 'coordinator', not 'remediation_reviewer'.
    assert credits == [
        {"login": "author", "type": "remediation_developer"},
        {"login": "reviewer1", "type": "coordinator"},
        {"login": "reviewer2", "type": "remediation_reviewer"},
    ]


def test_get_security_advisory_credits_self_review():
    github = mock.Mock()

    pulls_list = mock.Mock()
    pulls_list.content = json.dumps([{"number": 1, "user": {"login": "author"}}])
    github.rest.pulls.list.return_value = pulls_list

    reviews_list = mock.Mock()
    reviews_list.content = json.dumps([{"user": {"login": "author"}}])
    github.rest.pulls.list_reviews.return_value = reviews_list

    credits = app.get_security_advisory_credits(
        github=github,
        security_advisory={
            "private_fork": {
                "owner": {"login": "fork-owner"},
                "name": "fork-name",
            },
            "credits": [],
        },
    )

    # Developer is favored over reviewer.
    assert credits == [{"login": "author", "type": "remediation_developer"}]


@pytest.mark.parametrize("remove_credits", [(), ("reviewer1",), ("reviewer1", "reviewer2")])
def test_get_security_advisory_credits_no_change(remove_credits: tuple[str, ...]) -> None:
    github = mock.Mock()
    cve_api = mock.Mock()

    pulls_list = mock.Mock()
    pulls_list.content = json.dumps([{"number": 1, "user": {"login": "author"}}])
    github.rest.pulls.list.return_value = pulls_list

    reviews_list = mock.Mock()
    reviews_list.content = json.dumps([{"user": {"login": "reviewer1"}}, {"user": {"login": "reviewer2"}}])
    github.rest.pulls.list_reviews.return_value = reviews_list

    security_advisory = _create_advisory_dict("draft", "CVE-2026-1234", ["psrt"])
    security_advisory["private_fork"] = {
        "owner": {"login": "fork-owner"},
        "name": "fork-name",
    }
    security_advisory["credits"] = [
        # Deliberately out of sorting order.
        {"login": "reviewer2", "type": "remediation_reviewer"},
        {"login": "author", "type": "remediation_developer"},
        {"login": "reviewer1", "type": "coordinator"},
    ]

    if remove_credits:
        security_advisory["credits"] = [c for c in security_advisory["credits"] if c["login"] not in remove_credits]

    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [security_advisory]

        app.apply_to_repo(github, "owner", "repo", cve_api)

    if remove_credits:
        github.rest.security_advisories.update_repository_advisory.assert_called_once_with(
            owner="owner",
            repo="repo",
            ghsa_id="GHSA-xxxx-xxxx-xxxx",
            data={
                "credits": [
                    {"login": "author", "type": "remediation_developer"},
                    {"login": "reviewer1", "type": "remediation_reviewer"},
                    {"login": "reviewer2", "type": "remediation_reviewer"},
                ]
            },
        )
    else:  # Nothing to update.
        github.rest.security_advisories.update_repository_advisory.assert_not_called()


def test_reserve_one_cve_id(cve_reserve_response, cve_id, year) -> None:
    cve_api = mock.Mock()
    cve_api.reserve.return_value = cve_reserve_response

    assert app.reserve_one_cve(cve_api) == cve_id

    cve_api.reserve.assert_called_with(count=1, year=year, random=True)


def test_only_processes_installations_for_required_org(monkeypatch) -> None:
    monkeypatch.setenv("GH_CLIENT_ID", "123")
    monkeypatch.setenv("GH_CLIENT_PRIVATE_KEY", "a2V5")
    monkeypatch.setenv("CVE_USERNAME", "stan@python.org")
    monkeypatch.setenv("CVE_API_KEY", "key")
    monkeypatch.setenv("GH_REQUIRED_ORG", "python")

    github = mock.Mock()
    github.rest.paginate.return_value = [
        mock.Mock(id=1, account=mock.Mock(login="evil-org")),
        mock.Mock(id=2, account=mock.Mock(login="python")),
    ]
    github.with_auth.return_value.rest.paginate.return_value = []

    with (
        mock.patch("psrt_ghsa_bot.app.GitHub", return_value=github),
        mock.patch("psrt_ghsa_bot.app.CveApi"),
        mock.patch("psrt_ghsa_bot.app.apply_to_repo"),
    ):
        app.run()

    github.auth.as_installation.assert_called_once_with(2)


@pytest.mark.parametrize(
    "state,tags",
    list(
        itertools.product(
            ["PUBLISHED", "REJECTED"],
            [
                ["patch"],
                ["issue-tracking", "patch"],
                ["third-party-advisory", "patch", "exploit"],
                [],
                ["third-party-advisory"],
                ["issue-tracking", "mailing-list"],
            ],
        )
    ),
)
def test_ghsa_closed_when_cve_patch_published(show_cve_response, state, tags, cve_id) -> None:
    show_cve_response["cveMetadata"]["state"] = state
    show_cve_response["containers"]["cna"]["references"] = list(_build_cve_references(tags))
    github = mock.Mock()
    cve_api = mock.Mock()
    cve_api.show_cve_record.return_value = show_cve_response
    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [_create_advisory_dict("draft", cve_id, [])]
        app.apply_to_repo(github, "owner", "repo", cve_api)

    update = github.rest.security_advisories.update_repository_advisory.call_args
    try:
        new_state = update.kwargs["data"]["state"]
    except AttributeError, KeyError:
        new_state = None
    assert (new_state == "closed") == (state == "PUBLISHED" and "patch" in tags)


@pytest.mark.parametrize("state", ["closed", "published", "triage"])
def test_only_draft_ghsa_closed_on_cve(show_cve_response, state) -> None:
    show_cve_response["containers"]["cna"]["references"] = list(_build_cve_references(["patch"]))
    github = mock.Mock()
    cve_api = mock.Mock()
    cve_api.show_cve_record.return_value = show_cve_response
    with mock.patch("psrt_ghsa_bot.app.get_repository_advisories") as get_repo_advs:
        get_repo_advs.return_value = [_create_advisory_dict(state, cve_id, [])]
        app.apply_to_repo(github, "owner", "repo", cve_api)

    update = github.rest.security_advisories.update_repository_advisory.call_args
    try:
        new_state = update.kwargs["data"]["state"]
    except AttributeError, KeyError:
        pass  # We're testing the state didn't change, so no update is good.
    else:
        assert new_state == state


@pytest.mark.parametrize(
    "errcls",
    [
        req_exc.RequestException,
        req_exc.ConnectionError,
        req_exc.ConnectTimeout,
        req_exc.ReadTimeout,
    ],
)
def test_show_cve_errors_ignored(errcls, cve_id):
    cve_api = mock.Mock()
    cve_api.show_cve_record.side_effect = errcls("test error")
    assert list(app.iter_cve_refs_with_tags(cve_api, cve_id, {"patch"})) == []
    cve_api.show_cve_record.assert_called()


@pytest.mark.parametrize("code", ["bad_request", "internal_server_error"])
def test_show_cve_bad_responses_logged(code, cve_id):
    response = requests.Response()
    response.status_code = requests.codes[code]
    response.reason = code.replace("_", " ").title()
    cve_api = mock.Mock()
    cve_api.show_cve_record.side_effect = req_exc.HTTPError(response=response)
    with mock.patch("sentry_sdk.logger.warning") as logger:
        assert list(app.iter_cve_refs_with_tags(cve_api, cve_id, {"patch"})) == []
    cve_api.show_cve_record.assert_called()
    assert logger.call_args is not None
    log_kwargs = logger.call_args.kwargs
    assert log_kwargs.get("status_code") == response.status_code
    assert log_kwargs.get("reason") == response.reason
