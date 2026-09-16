variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "node_instance_type" {
  type    = string
  default = "t3.xlarge"
}

variable "node_capacity_type" {
  type    = string
  default = "SPOT"
}