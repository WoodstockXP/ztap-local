locals {
  realm_filename = basename(var.realm_file_path)
  labels         = var.tenant_label == "" ? { app = "keycloak" } : { app = "keycloak", tenant = var.tenant_label }
}

resource "kubernetes_config_map_v1" "realm" {
  metadata {
    name      = "ztap-realm"
    namespace = var.namespace
  }
  data = {
    (local.realm_filename) = file(var.realm_file_path)
  }
}

resource "kubernetes_deployment_v1" "keycloak" {
  metadata {
    name      = "keycloak"
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
          name  = "keycloak"
          image = "quay.io/keycloak/keycloak:latest"
          args  = ["start-dev", "--import-realm"]
          env {
            name  = "KC_BOOTSTRAP_ADMIN_USERNAME"
            value = "admin"
          }
          env {
            name  = "KC_BOOTSTRAP_ADMIN_PASSWORD"
            value = "admin"
          }
          port {
            container_port = 8080
          }
          volume_mount {
            name       = "realm-import"
            mount_path = "/opt/keycloak/data/import"
            read_only  = true
          }
        }
        volume {
          name = "realm-import"
          config_map {
            name = kubernetes_config_map_v1.realm.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "keycloak" {
  metadata {
    name      = "keycloak"
    namespace = var.namespace
  }
  spec {
    selector = local.labels
    port {
      port        = 8080
      target_port = 8080
    }
  }
}
