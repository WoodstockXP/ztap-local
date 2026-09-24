locals {
  namespaces = ["monitoring", "traffic-gen", "authorizer", "gateway-ingress", "inference", "tenant-a", "tenant-b"]
}

resource "kubernetes_network_policy_v1" "default_deny_all" {
  for_each = toset(local.namespaces)
  metadata {
    name      = "default-deny-all"
    namespace = each.value
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}

resource "kubernetes_network_policy_v1" "allow_dns" {
  for_each = toset(local.namespaces)
  metadata {
    name      = "allow-dns"
    namespace = each.value
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "kube-system" }
        }
      }
      ports {
        protocol = "UDP"
        port     = "53"
      }
      ports {
        protocol = "TCP"
        port     = "53"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_gateway_egress_to_authorizer" {
  metadata {
    name      = "allow-gateway-egress-to-authorizer"
    namespace = "gateway-ingress"
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "authorizer" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_agent_egress_to_authorizer" {
  for_each = toset(["tenant-a", "tenant-b"])
  metadata {
    name      = "allow-agent-egress-to-authorizer"
    namespace = each.value
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "authorizer" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_ingress_from_tenants_and_gateway" {
  metadata {
    name      = "allow-ingress-from-tenants-and-gateway"
    namespace = "authorizer"
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-a" }
        }
      }
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-b" }
        }
      }
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "gateway-ingress" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_agent_egress_to_gateway" {
  for_each = toset(["tenant-a", "tenant-b"])
  metadata {
    name      = "allow-agent-egress-to-gateway"
    namespace = each.value
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "gateway-ingress" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8001"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_ingress_from_tenants_gateway" {
  metadata {
    name      = "allow-ingress-from-tenants"
    namespace = "gateway-ingress"
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-a" }
        }
      }
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-b" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8001"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_agent_egress_to_inference" {
  for_each = toset(["tenant-a", "tenant-b"])
  metadata {
    name      = "allow-agent-egress-to-inference"
    namespace = each.value
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "inference" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "11434"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_ingress_from_tenants_inference" {
  metadata {
    name      = "allow-ingress-from-tenants"
    namespace = "inference"
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-a" }
        }
      }
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-b" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "11434"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_inference_egress_internet" {
  metadata {
    name      = "allow-inference-egress-internet"
    namespace = "inference"
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      ports {
        protocol = "TCP"
        port     = "443"
      }
    }
  }
}
