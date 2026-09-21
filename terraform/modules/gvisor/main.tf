resource "kubernetes_runtime_class_v1" "gvisor" {
  metadata {
    name = "gvisor"
  }
  handler = "runsc"
}