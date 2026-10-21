# SonarQube groups: <project-group>-admin and <project-group>-developer.
resource "sonarqube_group" "groups" {
  for_each    = local.group_tiers
  name        = each.key
  description = "GitLab ${each.value.project_group} access"
}

# One permission template per project group, matched by project key pattern.
resource "sonarqube_permission_template" "templates" {
  for_each            = local.project_groups
  name                = each.key
  description         = "Permission template for GitLab group(s): ${join(", ", [for s in each.value : s.scope])}"
  project_key_pattern = "${each.key}.*"
}

# Attach each group to its project group's template with the tier permissions.
resource "sonarqube_permissions" "template_permissions" {
  for_each    = local.group_tiers
  group_name  = sonarqube_group.groups[each.key].name
  template_id = sonarqube_permission_template.templates[each.value.project_group].id
  permissions = each.value.permissions
}

# Assign matched SonarQube users to their project group and tier.
resource "sonarqube_group_member" "members" {
  for_each   = local.assignments
  name       = each.value.group
  login_name = each.value.login

  depends_on = [sonarqube_group.groups]
}
