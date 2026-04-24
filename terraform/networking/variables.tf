variable "team_name" {
  type        = string
  description = "Name of the team being onboarded (e.g. team-phoenix)."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.team_name))
    error_message = "team_name must be lowercase alphanumeric/hyphens, starting with a letter."
  }
}

variable "region" {
  type        = string
  description = "AWS region to provision the landing zone in."
  default     = "us-east-1"
}
