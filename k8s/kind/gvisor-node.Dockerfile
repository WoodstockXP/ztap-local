ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN curl -fsSL https://storage.googleapis.com/gvisor/releases/release/latest/x86_64/runsc -o /usr/local/bin/runsc
RUN curl -fsSL https://storage.googleapis.com/gvisor/releases/release/latest/x86_64/containerd-shim-runsc-v1 -o /usr/local/bin/containerd-shim-runsc-v1
RUN chmod 0755 /usr/local/bin/runsc /usr/local/bin/containerd-shim-runsc-v1
