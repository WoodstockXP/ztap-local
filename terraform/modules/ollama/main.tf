resource "kubernetes_deployment_v1" "ollama" {
  metadata {
    name      = "ollama"
    namespace = var.namespace
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "ollama" }
    }
    template {
      metadata {
        labels = { app = "ollama" }
      }
      spec {
        node_selector = {
          "ztap.io/node-pool" = var.node_pool
        }
        container {
          name  = "ollama"
          image = "ollama/ollama:latest"
          port {
            container_port = 11434
          }
          volume_mount {
            name       = "ollama-data"
            mount_path = "/root/.ollama"
          }
          readiness_probe {
            tcp_socket {
              port = 11434
            }
            initial_delay_seconds = 5
            period_seconds         = 5
          }
        }
        volume {
          name = "ollama-data"
          empty_dir {}
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "ollama" {
  metadata {
    name      = "ollama"
    namespace = var.namespace
  }
  spec {
    selector = { app = "ollama" }
    port {
      port        = 11434
      target_port = 11434
    }
  }
}
