# SonarQube GitLab User Management

Terraform that provisions SonarQube groups, permission templates, and memberships for
GitLab (SaaS) project groups, from pre-generated snapshots — no live GitLab calls at
`plan`/`apply`. Two environments: **dev** and **prod**.

## Layout

```
modules/usermanagement/     # the logic (groups, templates, permissions, assignments)
environments/
  dev/                      # dev root: backend (dev state) + SonarQube provider + module call
  prod/                     # prod root: backend (prod state) + ...
config/config.yml           # shared: GitLab parent groups to onboard
scripts/                    # helper scripts + the generated access snapshot
  scan_gitlab_access.py     #   scan GitLab tree -> gitlab-access.json
  sonar_saml_users.py       #   SonarQube SAML email->login map
  sonar_version.py          #   resolve SonarQube server version
  gitlab-access.json        #   generated snapshot (consumed by Terraform)
```

Shared inputs (`config/config.yml`, `scripts/gitlab-access.json`) live in the repo. The
SonarQube host is the required `sonarqube_host` variable (no default); in CI it comes from
the GitHub environment variable `SONAR_HOST`. Each environment supplies its own admin token
and its own `sonar-saml-users.json`.

## Model

For each direct subgroup of a configured parent (`config/config.yml`), the module creates
`<group>-admin` and `<group>-developer` SonarQube groups and one template:

| SonarQube group     | GitLab role               | Permissions                                               |
| ------------------- | ------------------------- | --------------------------------------------------------- |
| `<group>-admin`     | Owner, Maintainer         | admin, issueadmin, securityhotspotadmin, codeviewer, user |
| `<group>-developer` | remaining, except Reporter | codeviewer                                                |

Key = subgroup leaf as-is (e.g. `derp-monitoring`); template pattern `derp-monitoring.*`.
A leaf that exists under both parents (e.g. `devops`) is unioned into one template.
Members are matched to **SAML** SonarQube accounts by email (`sonar-saml-users.json`).

## Run (per environment)

The scripts use the `requests` library: `pip install requests` first (CI installs it per job).

```bash
# 1. Refresh the shared GitLab snapshot (admin GitLab token), once for both envs:
export GITLAB_TOKEN="glpat-...admin..."
python3 scripts/scan_gitlab_access.py \
  -o scripts/gitlab-access.json                   # -> scripts/gitlab-access.json

# 2. Work inside the target environment (host is required; CI sets it from vars.SONAR_HOST):
cd environments/dev                               # or environments/prod
export TF_VAR_sonarqube_host="https://sonarqube-dev.srdops.com"   # the dev URL (prod differs)
export TF_VAR_sonarqube_token="squ_...admin..."

# 3. Generate this env's SAML map (SAML accounts only) into the env folder:
SONAR_HOST="$TF_VAR_sonarqube_host" SONAR_TOKEN="$TF_VAR_sonarqube_token" \
  python3 ../../scripts/sonar_saml_users.py        # -> ./sonar-saml-users.json

# 4. Apply:
terraform init
terraform plan
terraform apply
```

Re-run step 1 to refresh GitLab membership, step 3 after new SAML logins, then `apply`.

## Scripts

| Script                          | Purpose                                                           |
| ------------------------------- | ----------------------------------------------------------------- |
| `scripts/scan_gitlab_access.py` | Scan the GitLab tree -> `scripts/gitlab-access.json` (admin GitLab token). |
| `scripts/sonar_saml_users.py`   | SAML email->login map for an environment (admin SonarQube token). |
| `scripts/sonar_version.py`      | Resolve the server version for the provider (used by `providers.tf`). |
