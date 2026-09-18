resource "helm_release" "kube_prometheus_stack" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "87.21.0"
  namespace  = var.namespace
  set = [
    { name = "prometheus.prometheusSpec.nodeSelector.ztap\\.io/node-pool", value = var.node_pool },
    { name = "grafana.nodeSelector.ztap\\.io/node-pool", value = var.node_pool },
    { name = "alertmanager.alertmanagerSpec.nodeSelector.ztap\\.io/node-pool", value = var.node_pool },
    { name = "prometheusOperator.nodeSelector.ztap\\.io/node-pool", value = var.node_pool },
    { name = "kube-state-metrics.nodeSelector.ztap\\.io/node-pool", value = var.node_pool }
  ]
}

resource "helm_release" "otel_collector" {
  name       = "otel-collector"
  repository = "https://open-telemetry.github.io/opentelemetry-helm-charts"
  chart      = "opentelemetry-collector"
  version    = "0.173.1"
  namespace  = var.namespace
  set = [
    { name = "image.repository", value = "otel/opentelemetry-collector" },
    { name = "nodeSelector.ztap\\.io/node-pool", value = var.node_pool },
    { name = "mode", value = "deployment" },
    { name = "config.receivers.otlp.protocols.grpc.endpoint", value = "0.0.0.0:4317" },
    { name = "config.receivers.otlp.protocols.http.endpoint", value = "0.0.0.0:4318" },
    { name = "config.exporters.debug.verbosity", value = "detailed" },
    { name = "config.service.pipelines.traces.receivers[0]", value = "otlp" },
    { name = "config.service.pipelines.traces.exporters[0]", value = "debug" },
    { name = "config.service.pipelines.metrics.receivers[0]", value = "otlp" },
    { name = "config.service.pipelines.metrics.exporters[0]", value = "debug" }
  ]
  depends_on = [helm_release.kube_prometheus_stack]
}