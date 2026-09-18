variable "namespaces" {
  type = list(object({
    name   = string
    labels = map(string)
  }))
}