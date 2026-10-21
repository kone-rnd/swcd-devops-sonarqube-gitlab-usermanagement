# S3 backend for remote state (prod).
terraform {
  backend "s3" {
    bucket       = "kone-gh-terraform-project-state-bucket"
    key          = "gh-sonar/gitlab-usermanagement/prod.tfstate"
    region       = "eu-west-1"
    use_lockfile = true
  }
}
