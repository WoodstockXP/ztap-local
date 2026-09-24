resource "kubernetes_deployment_v1" "agent_sandbox" {
  metadata {
    name      = "agent-sandbox"
    namespace = var.namespace
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "agent-sandbox", tenant = var.tenant_label }
    }
    template {
      metadata {
        labels = { app = "agent-sandbox", tenant = var.tenant_label }
      }
      spec {
        runtime_class_name = var.gvisor_enabled ? "gvisor" : null
        node_selector = merge(
          { "ztap.io/node-pool" = var.tenant_label },
          var.gvisor_enabled ? { "ztap.io/gvisor" = "true" } : {}
        )
        container {
          name              = "agent-sandbox"
          image             = var.image
          image_pull_policy = "IfNotPresent"
          command           = ["sleep", "infinity"]
          env {
            name  = "ZTAP_KEYCLOAK_TOKEN_URL"
            value = var.keycloak_token_url
          }
          env {
            name  = "ZTAP_GATEWAY_URL"
            value = var.gateway_url
          }
          env {
            name  = "ZTAP_OLLAMA_BASE_URL"
            value = var.ollama_base_url
          }
          env {
            name  = "ZTAP_CLIENT_ID"
            value = var.client_id
          }
        }
      }
    }
  }
}