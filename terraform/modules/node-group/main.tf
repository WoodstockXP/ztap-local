locals {
  mime_boundary = "==BOUNDARY=="
  user_data_lines = [
    "MIME-Version: 1.0",
    "Content-Type: multipart/mixed; boundary=\"${local.mime_boundary}\"",
    "",
    "--${local.mime_boundary}",
    "Content-Type: text/x-shellscript; charset=\"us-ascii\"",
    "",
    var.bootstrap_script,
    "--${local.mime_boundary}--"
  ]
  user_data = base64encode(join("\n", local.user_data_lines))
}

resource "aws_launch_template" "this" {
  count       = var.bootstrap_script != "" ? 1 : 0
  name_prefix = "${var.cluster_name}-${var.pool_name}-"
  user_data   = local.user_data
}

resource "aws_iam_role" "node" {
  name = "${var.cluster_name}-${var.pool_name}-node-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "worker_node" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "cni" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_node_group" "this" {
  cluster_name    = var.cluster_name
  node_group_name = "${var.cluster_name}-${var.pool_name}"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  instance_types  = [var.instance_type]
  capacity_type   = var.capacity_type
  labels = merge(
    { "ztap.io/node-pool" = var.pool_name },
    var.gvisor_enabled ? { "ztap.io/gvisor" = "true" } : {}
  )
  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }
  dynamic "launch_template" {
    for_each = var.bootstrap_script != "" ? [1] : []
    content {
      id      = aws_launch_template.this[0].id
      version = aws_launch_template.this[0].latest_version
    }
  }
  depends_on = [
    aws_iam_role_policy_attachment.worker_node,
    aws_iam_role_policy_attachment.cni,
    aws_iam_role_policy_attachment.ecr_read
  ]
}