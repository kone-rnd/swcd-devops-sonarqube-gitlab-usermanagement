module "usermanagement" {
  source          = "../../modules/usermanagement"
  saml_users_file = abspath("${path.root}/sonar-saml-users.json")
}
