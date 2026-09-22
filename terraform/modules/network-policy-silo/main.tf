locals {
  namespaces = ["monitoring", "inference", "traffic-gen-a", "authorizer-a", "enforcer-a", "tenant-a", "traffic-gen-b", "authorizer-b", "enforcer-b", "tenant-b"]
  tenants    = ["a", "b"]
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

resource "kubernetes_network_policy_v1" "allow_enforcer_egress_to_authorizer" {
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-enforcer-egress-to-own-authorizer"
    namespace = "enforcer-${each.value}"
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "authorizer-${each.value}" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_ingress_authorizer_from_enforcer" {
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-ingress-from-own-enforcer"
    namespace = "authorizer-${each.value}"
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "enforcer-${each.value}" }
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
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-agent-egress-to-own-authorizer"
    namespace = "tenant-${each.value}"
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "authorizer-${each.value}" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_ingress_authorizer_from_tenant" {
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-ingress-from-own-tenant-agent"
    namespace = "authorizer-${each.value}"
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-${each.value}" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8080"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_agent_egress_to_enforcer" {
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-agent-egress-to-own-enforcer"
    namespace = "tenant-${each.value}"
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "enforcer-${each.value}" }
        }
      }
      ports {
        protocol = "TCP"
        port     = "8001"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_ingress_enforcer_from_tenant" {
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-ingress-from-own-tenant-agent"
    namespace = "enforcer-${each.value}"
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "tenant-${each.value}" }
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
  for_each = toset(local.tenants)
  metadata {
    name      = "allow-agent-egress-to-inference"
    namespace = "tenant-${each.value}"
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

resource "kubernetes_network_policy_v1" "allow_ingress_inference_from_tenants" {
  metadata {
    name      = "allow-ingress-from-both-tenants"
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
