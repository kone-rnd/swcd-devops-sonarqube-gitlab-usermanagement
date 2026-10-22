variable "sonarqube_host" {
  description = "SonarQube server URL (prod)"
  type        = string
}

variable "sonarqube_token" {
  description = "SonarQube admin token (prod)"
  type        = string
  sensitive   = true
}

variable "sonarqube_edition" {
  description = "SonarQube edition; set so the provider skips the /api/system/info probe."
  type        = string
  default     = "community"
}
