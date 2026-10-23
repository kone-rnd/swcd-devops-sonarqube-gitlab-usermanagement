variable "sonarqube_host" {
  description = "SonarQube server URL (dev)"
  type        = string
}


variable "sonarqube_edition" {
  description = "SonarQube edition; set so the provider skips the /api/system/info probe."
  type        = string
  default     = "community"
}
