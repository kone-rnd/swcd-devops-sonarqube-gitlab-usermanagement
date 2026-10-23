terraform {
  required_version = ">= 1.3"

  required_providers {
    sonarqube = {
      source  = "jdamata/sonarqube"
      version = "0.16.21"
    }
  }
}
