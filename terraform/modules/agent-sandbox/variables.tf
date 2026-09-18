variable "namespace" {
  type = string
}

variable "tenant_label" {
  type = string
}

variable "image" {
  type = string
}

variable "keycloak_token_url" {
  type = string
}

variable "gateway_url" {
  type = string
}

variable "ollama_base_url" {
  type = string
}

variable "client_id" {
  type    = string
  default = "ztap-gateway"
}
