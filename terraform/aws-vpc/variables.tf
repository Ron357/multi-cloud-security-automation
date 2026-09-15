variable "aws_region" {
  description = "AWS region to deploy the VPC into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used to prefix and tag all resources (e.g. 'msa' for multi-cloud-security-automation)."
  type        = string
  default     = "msa"
}

variable "environment" {
  description = "Environment label used in tags (e.g. dev, lab, prod)."
  type        = string
  default     = "lab"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of Availability Zones to spread subnets across. Must be <= the number of AZs available in the region."
  type        = number
  default     = 2
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets, one per AZ. Length must equal az_count."
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the private subnets, one per AZ. Length must equal az_count."
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "single_nat_gateway" {
  description = "If true, deploy one NAT Gateway shared by all private subnets (cheaper, lab-friendly). If false, deploy one NAT Gateway per AZ (production-grade, higher availability, higher cost)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags to merge into every resource."
  type        = map(string)
  default     = {}
}
