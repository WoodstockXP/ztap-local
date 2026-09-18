locals {
  labels = var.tenant_label == "" ? { app = "ztap-gateway" } : { app = "ztap-gateway", tenant = var.tenant_label }
}

resource "kubernetes_deployment_v1" "gateway" {
  metadata {
    name      = "ztap-gateway"
    namespace = var.namespace
  }
  spec {
    replicas = 1
    selector {
      match_labels = local.labels
    }
    template {
      metadata {
        labels = local.labels
      }
      spec {
        node_selector = {
          "ztap.io/node-pool" = var.node_pool
        }
        container {
          name              = "ztap-gateway"
          image             = var.image
          image_pull_policy = "IfNotPresent"
          command           = ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8001"]
          env {
            name  = "ZTAP_KEYCLOAK_ISSUER"
            value = var.keycloak_issuer
          }
          env {
            name  = "ZTAP_CLIENT_ID"
            value = var.client_id
          }
          env {
            name  = "ZTAP_AGENT_ID"
            value = var.agent_id
          }
          port {
            container_port = 8001
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "gateway" {
  metadata {
    name      = "ztap-gateway"
    namespace = var.namespace
  }
  spec {
    selector = local.labels
    port {
      port        = 8001
      target_port = 8001
    }
  }
}