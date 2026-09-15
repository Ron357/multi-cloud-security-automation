output "resource_group_name" {
  description = "Name of the resource group holding hub and spoke."
  value       = azurerm_resource_group.this.name
}

output "hub_vnet_id" {
  description = "ID of the hub VNet."
  value       = azurerm_virtual_network.hub.id
}

output "spoke_vnet_id" {
  description = "ID of the spoke VNet."
  value       = azurerm_virtual_network.spoke.id
}

output "hub_shared_subnet_id" {
  description = "ID of the hub's shared-services subnet."
  value       = azurerm_subnet.hub_shared.id
}

output "spoke_workload_subnet_id" {
  description = "ID of the spoke's workload subnet."
  value       = azurerm_subnet.spoke_workload.id
}
