variable "namespace" {
  type = string
}

variable "node_pool" {
  type = string
}

variable "image" {
  type = string
}

variable "keycloak_issuer" {
  type = string
}

variable "client_id" {
  type    = string
  default = "ztap-gateway"
}

variable "agent_id" {
  type    = string
  default = "invoice-agent-v2"
}

variable "tenant_label" {
  type    = string
  default = ""
}