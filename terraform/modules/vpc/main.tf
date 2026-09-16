locals {
  tenant_count = 2
  subnet_azs   = [for i in range(local.tenant_count) : var.availability_zones[i % length(var.availability_zones)]]
  subnet_cidrs = [for i in range(local.tenant_count) : cidrsubnet(var.cidr_block, 8, i)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name = "${var.cluster_name}-vpc"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags = {
    Name = "${var.cluster_name}-igw"
  }
}

resource "aws_subnet" "this" {
  for_each                = { for idx, cidr in local.subnet_cidrs : tostring(idx) => cidr }
  vpc_id                  = aws_vpc.this.id
  cidr_block               = each.value
  availability_zone       = local.subnet_azs[tonumber(each.key)]
  map_public_ip_on_launch = true
  tags = {
    Name                     = "${var.cluster_name}-subnet-${each.key}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_route_table" "this" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = {
    Name = "${var.cluster_name}-rt"
  }
}

resource "aws_route_table_association" "this" {
  for_each       = aws_subnet.this
  subnet_id      = each.value.id
  route_table_id = aws_route_table.this.id
}

resource "aws_security_group" "tenant" {
  for_each = var.subnet_per_tenant ? aws_subnet.this : {}
  name     = "${var.cluster_name}-sg-${each.key}"
  vpc_id   = aws_vpc.this.id
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    Name = "${var.cluster_name}-sg-${each.key}"
  }
}

resource "aws_security_group" "shared" {
  count = var.subnet_per_tenant ? 0 : 1
  name  = "${var.cluster_name}-sg-shared"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    Name = "${var.cluster_name}-sg-shared"
  }
}