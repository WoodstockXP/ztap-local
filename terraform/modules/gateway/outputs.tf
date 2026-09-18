output "service_name" {
  value = kubernetes_service_v1.gateway.metadata[0].name
}

output "namespace" {
  value = var.namespace
}