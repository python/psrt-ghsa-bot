# PSRT GHSA Bot

PSRT GHSA Bot is a GitHub App that automates the [Python Security Response Team
(PSRT)](https://devguide.python.org/security/psrt/)'s
handling of GitHub Security Advisories. It runs hourly (or by manual dispatch)
and, for every advisory it closes ones marked as completed, promotes accepted ones
from triage to draft, reserves CVE IDs, creates private forks, and adds the
PSRT team as collaborators.

It only processes installations owned by the account named in the `GH_REQUIRED_ORG`
environment variable; installations under any other user are skipped.
For that account it processes every repository the GitHub App is installed on.
The process is identical across repositories except that CVE IDs are only
reserved for repositories listed in the `CVE_ENABLED_REPOS` environment variable.

```mermaid
flowchart TD
    Start([Hourly cron or manual dispatch]):::entry --> Advs[For each repository security advisory]:::loop
    Advs --> S{"Advisory state?"}:::decision

    S -- Closed --> Skip([Skip advisory]):::terminal
    S -- Triage --> Collab
    S -- Draft --> Collab

    Collab{"PSRT missing as collaborators?"}:::decision
    Collab -- yes --> AddCollab[Add PSRT as collaborators]:::write --> Tag
    Collab -- no --> Tag

    Tag{"Summary has a completion tag?"}:::decision
    Tag -- yes --> Close[Close advisory]:::write --> Done([Continue to next advisory]):::terminal
    Tag -- "No, Triage" --> Accept{"Summary has an accept tag?"}:::decision
    Tag -- "No, Draft" --> Fork

    Accept -- yes --> ToDraft[Move to the draft state]:::write --> Fork
    Accept -- no --> Update

    Fork{"No private fork?"}:::decision
    Fork -- yes --> MkFork[Create private fork]:::write --> Cve
    Fork -- no --> Cve

    Cve{"No CVE ID assigned?"}:::decision
    Cve -- yes --> Reserve[Reserve a CVE ID]:::write --> Update
    Cve -- no --> Update

    Update[Update advisory]:::write --> Done

classDef entry stroke:#0C0,stroke-width:2px;
classDef loop stroke:#00C;
classDef decision stroke:#CC0;
classDef write stroke:#C0C;
classDef terminal stroke:#0C0;
```
