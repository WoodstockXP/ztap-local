resource "kubernetes_namespace_v1" "this" {
  for_each = { for ns in var.namespaces : ns.name => ns }
  metadata {
    name   = each.value.name
    labels = each.value.labels
  }
}