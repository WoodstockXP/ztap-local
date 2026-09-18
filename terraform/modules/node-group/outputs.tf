output "node_group_arn" {
  value = aws_eks_node_group.this.arn
}

output "node_role_arn" {
  value = aws_iam_role.node.arn
}