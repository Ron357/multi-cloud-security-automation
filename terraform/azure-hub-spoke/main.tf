terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}

locals {
  name = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# Resource group — one RG holds both hub and spoke for this lab. In a real
# enterprise layout the hub often lives in its own subscription/RG owned by
# a platform team, with spokes owned by workload teams.
# ---------------------------------------------------------------------------
resource "azurerm_resource_group" "this" {
  name     = "${local.name}-rg"
  location = var.location
  tags     = local.common_tags
}

# ---------------------------------------------------------------------------
# Hub VNet — holds shared services (e.g. a firewall, bastion, VPN gateway
# in a fuller build-out). This lab wires up the subnet and peering only.
# ---------------------------------------------------------------------------
resource "azurerm_virtual_network" "hub" {
  name                = "${local.name}-hub-vnet"
  address_space       = [var.hub_vnet_cidr]
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags
}

resource "azurerm_subnet" "hub_shared" {
  name                 = "shared-services"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.hub_subnet_cidr]
}

resource "azurerm_network_security_group" "hub_shared" {
  name                = "${local.name}-hub-shared-nsg"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags
}

resource "azurerm_subnet_network_security_group_association" "hub_shared" {
  subnet_id                 = azurerm_subnet.hub_shared.id
  network_security_group_id = azurerm_network_security_group.hub_shared.id
}

# ---------------------------------------------------------------------------
# Spoke VNet — holds workload resources, peered back to the hub for shared
# services access. Traffic between spokes would route through the hub in a
# full build-out (typically via a firewall/NVA), not directly spoke-to-spoke.
# ---------------------------------------------------------------------------
resource "azurerm_virtual_network" "spoke" {
  name                = "${local.name}-spoke-vnet"
  address_space       = [var.spoke_vnet_cidr]
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags
}

resource "azurerm_subnet" "spoke_workload" {
  name                 = "workload"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.spoke.name
  address_prefixes     = [var.spoke_subnet_cidr]
}

resource "azurerm_network_security_group" "spoke_workload" {
  name                = "${local.name}-spoke-workload-nsg"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags
}

resource "azurerm_subnet_network_security_group_association" "spoke_workload" {
  subnet_id                 = azurerm_subnet.spoke_workload.id
  network_security_group_id = azurerm_network_security_group.spoke_workload.id
}

# ---------------------------------------------------------------------------
# VNet peering — bidirectional, hub <-> spoke
# ---------------------------------------------------------------------------
resource "azurerm_virtual_network_peering" "hub_to_spoke" {
  name                      = "${local.name}-hub-to-spoke"
  resource_group_name       = azurerm_resource_group.this.name
  virtual_network_name      = azurerm_virtual_network.hub.name
  remote_virtual_network_id = azurerm_virtual_network.spoke.id

  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  allow_gateway_transit        = true
  use_remote_gateways          = false
}

resource "azurerm_virtual_network_peering" "spoke_to_hub" {
  name                      = "${local.name}-spoke-to-hub"
  resource_group_name       = azurerm_resource_group.this.name
  virtual_network_name      = azurerm_virtual_network.spoke.name
  remote_virtual_network_id = azurerm_virtual_network.hub.id

  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  allow_gateway_transit        = false
  use_remote_gateways          = false
}
