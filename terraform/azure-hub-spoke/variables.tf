variable "location" {
  description = "Azure region to deploy into."
  type        = string
  default     = "eastus"
}

variable "project_name" {
  description = "Short name used to prefix and tag all resources."
  type        = string
  default     = "msa"
}

variable "environment" {
  description = "Environment label used in tags (e.g. dev, lab, prod)."
  type        = string
  default     = "lab"
}

variable "hub_vnet_cidr" {
  description = "CIDR block for the hub VNet."
  type        = string
  default     = "10.1.0.0/16"
}

variable "hub_subnet_cidr" {
  description = "CIDR block for the hub's shared-services subnet."
  type        = string
  default     = "10.1.0.0/24"
}

variable "spoke_vnet_cidr" {
  description = "CIDR block for the spoke VNet."
  type        = string
  default     = "10.2.0.0/16"
}

variable "spoke_subnet_cidr" {
  description = "CIDR block for the spoke's workload subnet."
  type        = string
  default     = "10.2.0.0/24"
}

variable "tags" {
  description = "Additional tags to merge into every resource."
  type        = map(string)
  default     = {}
}
