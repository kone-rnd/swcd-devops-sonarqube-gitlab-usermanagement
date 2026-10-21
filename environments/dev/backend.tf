# S3 backend for remote state (dev).
terraform {
  backend "s3" {
    bucket       = "kone-gh-terraform-project-state-bucket"
    key          = "gh-sonar/gitlab-usermanagement/dev.tfstate"
    region       = "eu-west-1"
    use_lockfile = true
  }
}
