"""GitHub application that applies the PSRT process for GitHub Security Advisories."""

import base64
import datetime
import json
import os
import re
import time
import typing
import urllib.parse

from cvelib.cve_api import CveApi
from dotenv import load_dotenv
from githubkit import AppAuthStrategy, GitHub
from githubkit.exception import RequestFailed, RequestError

from psrt_ghsa_bot._sentry_monitoring import (
    MONITOR_SLUG_GHSA,
    STATUS_ERROR,
    STATUS_IN_PROGRESS,
    STATUS_OK,
    capture_checkin,
    capture_exception,
    init_sentry,
)

load_dotenv()

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
        # Capture the original exception in Sentry (private)
        # and emit a sanitized public exception.
        capture_exception()
        raise RuntimeError("Request to paginate advisories failed.")


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


def apply_to_repo(github: GitHub, owner: str, repo: str, cve_api: CveApi) -> None:
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
            except RequestFailed:
                # Capture the original exception in Sentry (private)
                # and emit a sanitized public exception.
                capture_exception()
                raise RuntimeError("Request to create a private fork failed") from None

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

        # Apply updates, if any, to the security advisory.
        if patch_data:
            try:
                github.rest.security_advisories.update_repository_advisory(
                    owner=owner,
                    repo=repo,
                    ghsa_id=ghsa_id,
                    data=patch_data,
                )
            except RequestFailed:
                # Capture the original exception in Sentry (private)
                # and emit a sanitized public exception.
                capture_exception()
                raise RuntimeError("Request to update advisory failed") from None
            print("       💾 Updated advisory")
        else:
            print("       ⏭️  No updates needed")

    if advisory_count == 0:
        print("    ℹ️  No security advisories found")


def run() -> None:
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

        repos = installation_github.rest.paginate(
            installation_github.rest.apps.list_repos_accessible_to_installation,
            map_func=lambda r: r.parsed_data.repositories,
        )
        for repo in repos:
            print(f"  Checking repo: {repo.owner.login}/{repo.name}")
            apply_to_repo(installation_github, repo.owner.login, repo.name, cve_api)

    print(f"\nDone! Processed {installation_count} installation(s).")


def main() -> None:
    # Report the cron run to Sentry so we're alerted if it fails or stops running.
    init_sentry()
    check_in_id = capture_checkin(MONITOR_SLUG_GHSA, STATUS_IN_PROGRESS)
    start_time = time.monotonic()
    try:
        run()
    except Exception:
        capture_checkin(
            MONITOR_SLUG_GHSA, STATUS_ERROR, duration=time.monotonic() - start_time, check_in_id=check_in_id
        )
        raise
    capture_checkin(MONITOR_SLUG_GHSA, STATUS_OK, duration=time.monotonic() - start_time, check_in_id=check_in_id)


if __name__ == "__main__":
    main()
