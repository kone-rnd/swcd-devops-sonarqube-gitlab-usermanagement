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
gitlab-access.json          # shared: GitLab access snapshot (same org for both envs)
services/                   # helper scripts (see below)
```

Shared inputs (`config/config.yml`, `gitlab-access.json`) live at the repo root. Each
environment supplies its own SonarQube host/token and its own `sonar-saml-users.json`.

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

```bash
# 1. Refresh the shared GitLab snapshot (admin GitLab token), once for both envs:
export TF_VAR_gitlab_token="glpat-...admin..."
python3 services/scan_gitlab_access.py            # -> gitlab-access.json

# 2. Work inside the target environment:
cd environments/dev                               # or environments/prod
export TF_VAR_sonarqube_host="https://sonarqube-dev.srdops.com"
export TF_VAR_sonarqube_token="squ_...admin..."

# 3. Generate this env's SAML map (SAML accounts only) into the env folder:
SONAR_HOST="$TF_VAR_sonarqube_host" SONAR_TOKEN="$TF_VAR_sonarqube_token" \
  python3 ../../services/sonar_saml_users.py       # -> ./sonar-saml-users.json

# 4. Apply:
terraform init
terraform plan
terraform apply
```

Re-run step 1 to refresh GitLab membership, step 3 after new SAML logins, then `apply`.

## Scripts

| Script                              | Purpose                                                        |
| ----------------------------------- | -------------------------------------------------------------- |
| `services/scan_gitlab_access.py`    | Scan the GitLab tree -> `gitlab-access.json` (admin token).    |
| `services/sonar_saml_users.py`      | SAML email->login map for an environment (admin SonarQube token). |
| `services/convert_to_user_format.py`| Convert an older nested export into the snapshot format.       |
