output "service_name" {
  value = kubernetes_service_v1.ollama.metadata[0].name
}

output "namespace" {
  value = var.namespace
}
