resource "helm_release" "cilium" {
  name       = "cilium"
  repository = "https://helm.cilium.io/"
  chart      = "cilium"
  namespace  = "kube-system"
  set = [
    { name = "eni.enabled", value = "true" },
    { name = "ipam.mode", value = "eni" },
    { name = "egressMasqueradeInterfaces", value = "eth0" },
    { name = "tunnel", value = "disabled" },
    { name = "hubble.enabled", value = "true" },
    { name = "hubble.relay.enabled", value = "true" },
    { name = "hubble.ui.enabled", value = "true" }
  ]
}

resource "kubernetes_manifest" "tenant_default_deny" {
  for_each = toset(var.tenant_namespaces)
  manifest = {
    apiVersion = "cilium.io/v2"
    kind       = "CiliumNetworkPolicy"
    metadata = {
      name      = "default-deny-cross-tenant"
      namespace = each.value
    }
    spec = {
      endpointSelector = {}
      ingress = [
        {
          fromEndpoints = [
            {
              matchLabels = {
                "k8s:io.kubernetes.pod.namespace" = each.value
              }
            }
          ]
        }
      ]
    }
  }
  depends_on = [helm_release.cilium]
}