locals {
  node_pools = {
    monitoring = {
      instance_type  = "t3.xlarge"
      gvisor_enabled = false
      desired_size   = 1
      min_size       = 1
      max_size       = 2
    }
    inference = {
      instance_type  = var.inference_instance_type
      gvisor_enabled = false
      desired_size   = 1
      min_size       = 1
      max_size       = 1
    }
    tenant-a = {
      instance_type  = "t3.xlarge"
      gvisor_enabled = true
      desired_size   = 1
      min_size       = 1
      max_size       = 2
    }
    tenant-b = {
      instance_type  = "t3.xlarge"
      gvisor_enabled = true
      desired_size   = 1
      min_size       = 1
      max_size       = 2
    }
  }

  namespaces = [
    { name = "monitoring", labels = { "ztap.io/topology" = "silo" } },
    { name = "inference", labels = { "ztap.io/topology" = "silo" } },
    { name = "traffic-gen-a", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-a" } },
    { name = "authorizer-a", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-a" } },
    { name = "enforcer-a", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-a" } },
    { name = "tenant-a", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-a" } },
    { name = "traffic-gen-b", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-b" } },
    { name = "authorizer-b", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-b" } },
    { name = "enforcer-b", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-b" } },
    { name = "tenant-b", labels = { "ztap.io/topology" = "silo", "ztap.io/tenant" = "tenant-b" } }
  ]
}

module "vpc" {
  source             = "../../modules/vpc"
  cluster_name       = "ztap-silo"
  subnet_per_tenant  = true
  availability_zones = var.availability_zones
}

module "eks_cluster" {
  source       = "../../modules/eks-cluster"
  cluster_name = "ztap-silo"
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.subnet_ids
}

module "node_group" {
  source         = "../../modules/node-group"
  for_each       = local.node_pools
  cluster_name   = module.eks_cluster.cluster_name
  pool_name      = each.key
  gvisor_enabled = each.value.gvisor_enabled
  subnet_ids     = module.vpc.subnet_ids
  instance_type  = each.value.instance_type
  desired_size   = each.value.desired_size
  min_size       = each.value.min_size
  max_size       = each.value.max_size
  capacity_type  = var.node_capacity_type
}

module "namespaces" {
  source     = "../../modules/namespaces"
  namespaces = local.namespaces
}

module "cilium" {
  source            = "../../modules/cilium"
  cluster_name      = module.eks_cluster.cluster_name
  tenant_namespaces = ["tenant-a", "tenant-b"]
  providers = {
    helm       = helm
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces]
}

module "ecr" {
  source          = "../../modules/ecr"
  repository_name = "ztap-app"
}

module "gvisor" {
  source = "../../modules/gvisor"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group]
}

module "network_policy" {
  source = "../../modules/network-policy-silo"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.namespaces, module.cilium]
}

module "keycloak_a" {
  source          = "../../modules/keycloak"
  namespace       = "authorizer-a"
  node_pool       = "tenant-a"
  tenant_label    = "tenant-a"
  realm_file_path = "${path.root}/../../../keycloak/ztap-realm-tenant-a.json"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces]
}

module "keycloak_b" {
  source          = "../../modules/keycloak"
  namespace       = "authorizer-b"
  node_pool       = "tenant-b"
  tenant_label    = "tenant-b"
  realm_file_path = "${path.root}/../../../keycloak/ztap-realm-tenant-b.json"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces]
}

module "gateway_a" {
  source          = "../../modules/gateway"
  namespace       = "enforcer-a"
  node_pool       = "tenant-a"
  tenant_label    = "tenant-a"
  image           = "${module.ecr.repository_url}:latest"
  keycloak_issuer = "http://${module.keycloak_a.service_name}.${module.keycloak_a.namespace}.svc.cluster.local:8080/realms/ztap-tenant-a"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces, module.keycloak_a]
}

module "gateway_b" {
  source          = "../../modules/gateway"
  namespace       = "enforcer-b"
  node_pool       = "tenant-b"
  tenant_label    = "tenant-b"
  image           = "${module.ecr.repository_url}:latest"
  keycloak_issuer = "http://${module.keycloak_b.service_name}.${module.keycloak_b.namespace}.svc.cluster.local:8080/realms/ztap-tenant-b"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces, module.keycloak_b]
}

module "ollama" {
  source = "../../modules/ollama"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces]
}

module "agent_sandbox_a" {
  source             = "../../modules/agent-sandbox"
  namespace          = "tenant-a"
  tenant_label       = "tenant-a"
  gvisor_enabled     = false
  image              = "${module.ecr.repository_url}:latest"
  keycloak_token_url = "http://${module.keycloak_a.service_name}.${module.keycloak_a.namespace}.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token"
  gateway_url        = "http://${module.gateway_a.service_name}.${module.gateway_a.namespace}.svc.cluster.local:8001/invoke"
  ollama_base_url    = "http://${module.ollama.service_name}.${module.ollama.namespace}.svc.cluster.local:11434/v1/"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.gvisor, module.network_policy, module.keycloak_a, module.gateway_a, module.ollama]
}

module "agent_sandbox_b" {
  source             = "../../modules/agent-sandbox"
  namespace          = "tenant-b"
  tenant_label       = "tenant-b"
  gvisor_enabled     = false
  image              = "${module.ecr.repository_url}:latest"
  keycloak_token_url = "http://${module.keycloak_b.service_name}.${module.keycloak_b.namespace}.svc.cluster.local:8080/realms/ztap-tenant-b/protocol/openid-connect/token"
  gateway_url        = "http://${module.gateway_b.service_name}.${module.gateway_b.namespace}.svc.cluster.local:8001/invoke"
  ollama_base_url    = "http://${module.ollama.service_name}.${module.ollama.namespace}.svc.cluster.local:11434/v1/"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.gvisor, module.network_policy, module.keycloak_b, module.gateway_b, module.ollama]
}
