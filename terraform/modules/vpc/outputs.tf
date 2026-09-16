output "vpc_id" {
  value = aws_vpc.this.id
}

output "subnet_ids" {
  value = [for s in aws_subnet.this : s.id]
}

output "security_group_ids" {
  value = var.subnet_per_tenant ? [for sg in aws_security_group.tenant : sg.id] : [aws_security_group.shared[0].id]
}