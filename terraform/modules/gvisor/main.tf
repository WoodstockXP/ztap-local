resource "kubernetes_runtime_class_v1" "gvisor" {
  metadata {
    name = "gvisor"
  }
  handler = "runsc"
}

resource "kubernetes_daemon_set_v1" "gvisor_installer" {
  metadata {
    name      = "gvisor-installer"
    namespace = "kube-system"
  }
  spec {
    selector {
      match_labels = { app = "gvisor-installer" }
    }
    template {
      metadata {
        labels = { app = "gvisor-installer" }
      }
      spec {
        node_selector = {
          "ztap.io/gvisor" = "true"
        }
        host_pid = true
        container {
          name  = "installer"
          image = "busybox:1.36"
          security_context {
            privileged = true
          }
          command = ["chroot", "/host", "sh", "-c"]
          args = [
            "mkdir -p /etc/containerd/conf.d; grep -q runtimes.runsc /etc/containerd/conf.d/runsc.toml 2>/dev/null || { wget -q https://storage.googleapis.com/gvisor/releases/release/latest/x86_64/runsc -O /usr/local/bin/runsc; chmod 0755 /usr/local/bin/runsc; wget -q https://storage.googleapis.com/gvisor/releases/release/latest/x86_64/containerd-shim-runsc-v1 -O /usr/local/bin/containerd-shim-runsc-v1; chmod 0755 /usr/local/bin/containerd-shim-runsc-v1; printf '%s\\n' \"[plugins.'io.containerd.cri.v1.runtime'.containerd.runtimes.runsc]\" \"runtime_type = 'io.containerd.runsc.v1'\" > /etc/containerd/conf.d/runsc.toml; systemctl restart containerd || echo SYSTEMCTL_RESTART_FAILED; }; sleep infinity"
          ]
          volume_mount {
            name              = "host-root"
            mount_path        = "/host"
            mount_propagation = "HostToContainer"
          }
        }
        volume {
          name = "host-root"
          host_path {
            path = "/"
          }
        }
      }
    }
  }
  depends_on = [kubernetes_runtime_class_v1.gvisor]
}