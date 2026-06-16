"""GitHub application which applies the PSRT process for GitHub Security Advisories."""

import base64
import csv
import datetime
import json
import os
import re
import typing
import urllib.parse

import urllib3
from cvelib.cve_api import CveApi
from dotenv import load_dotenv
from githubkit import AppAuthStrategy, GitHub
from githubkit.exception import RequestFailed, RequestError

load_dotenv()

PSRT_GITHUB_TEAM_ORG = "python"
PSRT_GITHUB_TEAM_SLUG = "psrt"
COMPLETION_TAGS = (
    "CLOSE",
    "CLOSED",
    "COMPLETE",
    "COMPLETED",
    "NOTPLANNED",
    "INVALID",
    "DUPLICATE",
)


def load_psrt_members_from_devguide() -> set[str]:
    """The PSRT GitHub team only supports adding users that are
    already within the 'python' GitHub org. This allows users
    that aren't in the org team to be added automatically to
    GHSA advisories.
    """
    psrt_csv_url = "https://raw.githubusercontent.com/python/devguide/refs/heads/main/security/psrt.csv"
    resp = urllib3.request(
        "GET", psrt_csv_url, timeout=10, redirect=False, retries=urllib3.Retry(total=5, backoff_factor=2)
    )
    if resp.status != 200:
        raise RuntimeError(
            f"Couldn't resolve PSRT members from python/devguide (status={resp.status} data={resp.data[:500]})"
        )
    rows = csv.reader(resp.data.decode().splitlines())
    return {github_login.lower() for _, github_login, *_ in rows}


def load_psrt_members_from_github(github: GitHub) -> set[str]:
    """Loads the GitHub usernames from the PSRT team on GitHub"""
    team_members = github.rest.teams.list_members_in_org(
        org=PSRT_GITHUB_TEAM_ORG,
        team_slug=PSRT_GITHUB_TEAM_SLUG,
        per_page=100,
    )
    return {member.login.lower() for member in team_members.parsed_data}


def get_repository_advisories(
    github: GitHub,
    owner: str,
    repo: str,
) -> typing.Iterable[dict[str, typing.Any]]:
    """Lists repository security advisories using the REST API."""

    try:
        # We can't use the GitHubKit pagination helper because
        # of Pydantic validation issues. We manually paginate instead.
        response = github.rest.security_advisories.list_repository_advisories(
            owner=owner,
            repo=repo,
            per_page=100,
        )
        next_url = None
        while True:
            # Parse JSON directly to bypass Pydantic validation
            advisories = json.loads(response.content)
            for advisory in advisories:
                yield advisory

            # Find the 'Next' URL for pagination. If the
            # URL exists we need to use this URL as the
            # 'list_security_advisories()' URL is completely
            # different to the 'Next' URL and the GitHub API blows up
            # if we pass '?after=...' as a parameter to
            # 'list_security_advisories()' :shrug:
            link_header = response.headers.get("Link", "")
            if mat := re.search(r'<([^>]+)>; rel="next"', link_header):
                next_url = mat.group(1)
            if not next_url:
                break

            # To avoid double-percent-quoting the 'after' parameter in
            # our request we unquote the value first before
            # sending it back into an HTTP client.
            after = urllib.parse.unquote(re.search(r"after=([^&]+)", next_url).group(1))
            # Remove params, we add them back in the request.
            next_url = next_url.split("?", 1)[0]

            response = github_client_request(
                client=github.rest.security_advisories,
                method="GET",
                url=next_url,
                params={"per_page": 100, "after": after},
            )
            next_url = None  # Reset for next loop.
    except RequestFailed as e:
        # 404 means no advisories or no access - that's okay
        if e.response.status_code == 404:
            return
        raise


def github_client_request(client: typing.Any, method: str, url: str, params: dict[str, str | int]) -> typing.Any:
    """Sends a raw HTTP request using a GitHub API client"""
    headers = {"X-GitHub-Api-Version": client._REST_API_VERSION}
    return client._github.request(
        method,
        url,
        params=params,
        headers=headers,
        error_models={
            "400": RequestError,
            "404": RequestError,
        },
    )


def reserve_one_cve(cve_api: CveApi) -> str:
    """Reserves a single CVE ID"""
    resp = cve_api.reserve(count=1, random=True, year=str(datetime.date.today().year))
    cve_ids = [cve["cve_id"] for cve in resp["cve_ids"]]
    assert len(cve_ids) == 1
    return cve_ids[0]


def apply_to_repo(
    github: GitHub, owner: str, repo: str, cve_api: CveApi, *, collaborating_users: set[str] | None = None
) -> None:
    """Applies the PSRT GitHub Security Advisory process to the repository."""
    security_advisories = get_repository_advisories(github, owner, repo)
    advisory_count = 0
    for security_advisory in security_advisories:
        advisory_count += 1
        ghsa_id = security_advisory["ghsa_id"]
        state = security_advisory["state"]

        # We only operate on in-progress security advisories.
        if state not in ("triage", "draft"):
            print(f"    ⏭️  Skipping {ghsa_id} (state: {state})")
            continue

        print(f"    📋 Processing {ghsa_id} (state: {state})")

        # If the summary contains a completion tag then we can close the ticket.
        summary = security_advisory.get("summary", "")
        if re.search(rf"\[(?:{'|'.join(COMPLETION_TAGS)})\]", summary.upper()) is not None:
            github.rest.security_advisories.update_repository_advisory(
                owner=owner,
                repo=repo,
                ghsa_id=ghsa_id,
                data={"state": "closed"},
            )
            print(f"       🧹 Closed {ghsa_id}")
            continue

        # Maintain a dictionary of updates to make and then submit them all at once.
        patch_data = {}

        # If the summary contains '[ACCEPT{ED}]' we can move the ticket to draft
        if state == "triage" and re.search(r"\[ACCEPT(?:ED)?\]", summary.upper()) is not None:
            patch_data["state"] = state = "draft"
            print(f"       ✅ Will accept {ghsa_id}")

        # Advisories that are in the 'draft' state without a private
        # fork active will have a fork requested.
        if state == "draft" and security_advisory.get("private_fork") is None:
            print("       🔨 No private fork, creating a private fork")
            try:
                github.rest.security_advisories.create_fork(
                    owner=owner,
                    repo=repo,
                    ghsa_id=ghsa_id,
                )
            except RequestFailed as e:
                print(f"       ⚠️ Error creating private fork: {e.response.json()}")
                raise e

        # Advisories that are in the 'draft' state without a CVE ID
        # should have one allocated by the PSF CVE Numbering Authority.
        if state == "draft" and security_advisory.get("cve_id") is None:
            cve_id = reserve_one_cve(cve_api)
            patch_data["cve_id"] = cve_id
            print(f"       ✅ Will reserve CVE ID: {cve_id}")

        collaborating_teams = {team["slug"] for team in security_advisory["collaborating_teams"]}
        if PSRT_GITHUB_TEAM_SLUG not in collaborating_teams:
            collaborating_teams.add(PSRT_GITHUB_TEAM_SLUG)
            patch_data["collaborating_teams"] = sorted(collaborating_teams)
            print(f"       ➕ Will ensure team present: {PSRT_GITHUB_TEAM_SLUG}")

        if collaborating_users:
            # Determine if we set the 'collaborating_users' field
            # at all by seeing if there are missing users on the
            # advisory. Preserve the old list, as this is edited
            # manually by coordinators.
            prev_collaborating_users = {user["login"].lower() for user in security_advisory["collaborating_users"]}
            if collaborating_users - prev_collaborating_users:
                # Sorting is only done for consistency's sake in testing.
                new_collaborating_users = sorted(collaborating_users | prev_collaborating_users)
                patch_data["collaborating_users"] = new_collaborating_users
                print(f"       ➕ Will ensure users are present: {new_collaborating_users}")

        # Apply updates, if any, to the security advisory.
        if patch_data:
            try:
                github.rest.security_advisories.update_repository_advisory(
                    owner=owner,
                    repo=repo,
                    ghsa_id=ghsa_id,
                    data=patch_data,
                )
            except RequestFailed as e:
                print(f"       ⚠️ Error updating advisory: {e.response.json()}")
                raise e
            print("       💾 Updated advisory")
        else:
            print("       ⏭️  No updates needed")

    if advisory_count == 0:
        print("    ℹ️  No security advisories found")


def main() -> None:
    print("Starting PSRT GitHub Security Advisory bot...")
    gh_client_private_key = base64.b64decode(os.environ["GH_CLIENT_PRIVATE_KEY"]).decode().strip()
    github = GitHub(
        AppAuthStrategy(os.environ["GH_CLIENT_ID"], gh_client_private_key),
    )
    cve_api = CveApi(
        org="PSF",
        username=os.environ["CVE_USERNAME"],
        api_key=os.environ["CVE_API_KEY"],
        env=os.environ.get("CVE_ENV", "prod"),
    )

    psrt_members_devguide: set[str] | None = None
    psrt_members_github: set[str] | None = None

    def fetch_collaborating_users(installation_github: GitHub) -> set[str]:
        nonlocal psrt_members_github, psrt_members_devguide

        # Only run the fetching step once.
        if psrt_members_github is None or psrt_members_devguide is None:
            print("Fetching PSRT members from Developer Guide...")
            psrt_members_devguide = load_psrt_members_from_devguide()

            print("Fetching PSRT members from GitHub Team...")
            psrt_members_github = load_psrt_members_from_github(installation_github)

        # Determine which PSRT members need to be added as
        # 'collaborating_users' to advisories due to not being
        # in the GitHub Team and Organization.
        psrt_members_not_in_github = set(psrt_members_devguide - psrt_members_github)
        print(f"PSRT members not in GitHub Team: {', '.join(sorted(psrt_members_not_in_github))}")
        return psrt_members_not_in_github

    print("Fetching installations...")
    # Apply to all repositories for each installation.
    installations = github.rest.paginate(
        github.rest.apps.list_installations,
    )
    installation_count = 0
    for installation_data in installations:
        installation_count += 1
        print(f"\nProcessing installation {installation_count}: {installation_data.account.login}")

        installation_github = github.with_auth(
            github.auth.as_installation(installation_data.id),
        )

        collaborating_users = fetch_collaborating_users(installation_github)
        repos = installation_github.rest.paginate(
            installation_github.rest.apps.list_repos_accessible_to_installation,
            map_func=lambda r: r.parsed_data.repositories,
        )
        for repo in repos:
            print(f"  Checking repo: {repo.owner.login}/{repo.name}")
            apply_to_repo(
                installation_github, repo.owner.login, repo.name, cve_api, collaborating_users=collaborating_users
            )

    print(f"\nDone! Processed {installation_count} installation(s).")


if __name__ == "__main__":
    main()
