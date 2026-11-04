# PSRT GHSA Bot

PSRT GHSA Bot is a GitHub App that automates the [Python Security Response Team
(PSRT)](https://devguide.python.org/security/psrt/)'s
handling of GitHub Security Advisories. It runs hourly (or by manual dispatch)
and does housekeeping on every advisory.

* For newly accepted advisories, it reserves a CVE ID, creates a private
  fork, and adds the PSRT team as collaborators.
* For accepted advisories, if the associated CVE has been published with
  a patch, it closes the advisory.

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
    S -- Draft --> Fork

    Fork{"No private fork?"}:::decision
    Fork -- yes --> MkFork[Create private fork]:::write --> CveId
    Fork -- no --> CveId

    CveId{"CVE ID assigned?"}:::decision
    CveId -- yes --> CveDone
    CveId -- no --> Reserve[Reserve a CVE ID]:::write --> Collab

    CveDone{"CVE published with patch?"}:::decision
    CveDone -- yes --> Close[Close advisory]:::write --> Collab
    CveDone -- no --> Collab

    Collab{"PSRT missing as collaborators?"}:::decision
    Collab -- yes --> AddCollab[Add PSRT as collaborators]:::write --> Credits
    Collab -- no --> Credits

    Credits[For each user associated with a pull request]:::loop --> CheckCredit
    CheckCredit{"User credited on advisory?"}:::decision
    CheckCredit -- yes --> Update
    CheckCredit -- no --> AddCredit[Add user to advisory credits]:::write --> Update

    Update[Update advisory]:::terminal

classDef entry stroke:#0C0,stroke-width:2px;
classDef loop stroke:#00C;
classDef decision stroke:#CC0;
classDef write stroke:#C0C;
classDef terminal stroke:#0C0;
```
