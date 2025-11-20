"""GitHub application which applies the PSRT process for GitHub Security Advisories."""

import base64
import datetime
import json
import os
import typing
from datetime import UTC
from http import HTTPStatus

from cvelib.cve_api import CveApi
from dotenv import load_dotenv
from githubkit import AppAuthStrategy, GitHub
from githubkit.exception import RequestFailed

load_dotenv()


PSRT_GITHUB_TEAM_SLUG = "psrt"  # TODO: configurable


def get_repository_advisories(
    github: GitHub,
    owner: str,
    repo: str,
) -> typing.Iterable[dict[str, typing.Any]]:
    """Lists repository security advisories using the REST API."""
    try:
        # Use direct request instead of paginate to avoid validation issues
        response = github.rest.security_advisories.list_repository_advisories(
            owner=owner,
            repo=repo,
        )
        # Parse JSON directly to bypass Pydantic validation
        advisories = json.loads(response.content)
        yield from advisories
    except RequestFailed as e:
        # 404 means no advisories or no access - that's okay
        if e.response.status_code == HTTPStatus.NOT_FOUND:
            return
        raise


def reserve_one_cve(cve_api: CveApi) -> str:
    """Reserves a single CVE ID."""
    resp = cve_api.reserve(count=1, random=True, year=str(datetime.datetime.now(tz=UTC).year))
    cve_ids = [cve["cve_id"] for cve in resp["cve_ids"]]
    if len(cve_ids) != 1:
        msg = f"Expected 1 CVE ID, got {len(cve_ids)}"
        raise ValueError(msg)
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
            continue

        # Maintain a dictionary of updates to make and then submit them all at once.
        patch_data = {}

        # Advisories that are in the 'draft' state without a CVE ID
        # should have one allocated by the PSF CVE Numbering Authority.
        if state == "draft" and security_advisory.get("cve_id") is None:
            cve_id = reserve_one_cve(cve_api)
            patch_data["cve_id"] = cve_id

        patch_data["collaborating_teams"] = [PSRT_GITHUB_TEAM_SLUG]

        # Apply updates, if any, to the security advisory.
        if patch_data:
            github.rest.security_advisories.update_repository_advisory(
                owner=owner,
                repo=repo,
                ghsa_id=ghsa_id,
                data=patch_data,
            )
        else:
            pass

    if advisory_count == 0:
        pass


def main() -> None:
    """Main entry point for cron.yml."""
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

    # Apply to all repositories for each installation.
    installations = github.rest.paginate(
        github.rest.apps.list_installations,
    )
    for _installation_count, installation_data in enumerate(installations, start=1):
        installation_github = github.with_auth(
            github.auth.as_installation(installation_data.id),
        )
        repos = installation_github.rest.paginate(
            installation_github.rest.apps.list_repos_accessible_to_installation,
            map_func=lambda r: r.parsed_data.repositories,
        )
        for repo in repos:
            apply_to_repo(installation_github, repo.owner.login, repo.name, cve_api)


if __name__ == "__main__":
    main()
