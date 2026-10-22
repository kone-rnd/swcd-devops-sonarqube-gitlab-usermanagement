terraform {
  required_version = ">= 1.3"

  required_providers {
    sonarqube = {
      source  = "jdamata/sonarqube"
      version = "0.16.21"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2.3"
    }
  }
}

# Resolve the server version from the unrestricted /api/server/version endpoint, so
# the provider skips the privileged /api/system/info probe and no version is manual.
data "external" "sonar_version" {
  program = ["python3", "${path.module}/../../scripts/sonar_version.py"]
  query   = { host = var.sonarqube_host }
}

provider "sonarqube" {
  host              = var.sonarqube_host
  token             = var.sonarqube_token
  installed_edition = var.sonarqube_edition
  installed_version = data.external.sonar_version.result.version
}
