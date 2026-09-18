locals {
  node_pools = {
    shared-services = {
      instance_type  = "t3.xlarge"
      gvisor_enabled = false
      desired_size   = 1
      min_size       = 1
      max_size       = 2
    }
    security-control = {
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
    { name = "monitoring", labels = { "ztap.io/topology" = "bridge" } },
    { name = "traffic-gen", labels = { "ztap.io/topology" = "bridge" } },
    { name = "authorizer", labels = { "ztap.io/topology" = "bridge" } },
    { name = "gateway-ingress", labels = { "ztap.io/topology" = "bridge" } },
    { name = "inference", labels = { "ztap.io/topology" = "bridge" } },
    { name = "tenant-a", labels = { "ztap.io/topology" = "bridge", "ztap.io/tenant" = "tenant-a" } },
    { name = "tenant-b", labels = { "ztap.io/topology" = "bridge", "ztap.io/tenant" = "tenant-b" } }
  ]
}

module "vpc" {
  source             = "../../modules/vpc"
  cluster_name       = "ztap-bridge"
  subnet_per_tenant  = false
  availability_zones = var.availability_zones
}

module "eks_cluster" {
  source       = "../../modules/eks-cluster"
  cluster_name = "ztap-bridge"
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

module "keycloak" {
  source          = "../../modules/keycloak"
  namespace       = "authorizer"
  node_pool       = "shared-services"
  realm_file_path = "${path.root}/../../../keycloak/ztap-realm.json"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces]
}

module "ecr" {
  source          = "../../modules/ecr"
  repository_name = "ztap-app"
}

module "gateway" {
  source          = "../../modules/gateway"
  namespace       = "gateway-ingress"
  node_pool       = "security-control"
  image           = "${module.ecr.repository_url}:latest"
  keycloak_issuer = "http://${module.keycloak.service_name}.${module.keycloak.namespace}.svc.cluster.local:8080/realms/ztap"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces, module.keycloak]
}

module "ollama" {
  source = "../../modules/ollama"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group, module.namespaces]
}

module "observability" {
  source = "../../modules/observability"
  providers = {
    helm = helm
  }
  depends_on = [module.node_group, module.namespaces]
}

module "network_policy" {
  source = "../../modules/network-policy"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.namespaces, module.cilium]
}

module "gvisor" {
  source = "../../modules/gvisor"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.node_group]
}

module "agent_sandbox_a" {
  source              = "../../modules/agent-sandbox"
  namespace           = "tenant-a"
  tenant_label        = "tenant-a"
  image               = "${module.ecr.repository_url}:latest"
  keycloak_token_url  = "http://${module.keycloak.service_name}.${module.keycloak.namespace}.svc.cluster.local:8080/realms/ztap/protocol/openid-connect/token"
  gateway_url         = "http://${module.gateway.service_name}.${module.gateway.namespace}.svc.cluster.local:8001/invoke"
  ollama_base_url     = "http://${module.ollama.service_name}.${module.ollama.namespace}.svc.cluster.local:11434/v1/"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.gvisor, module.network_policy, module.keycloak, module.gateway, module.ollama]
}

module "agent_sandbox_b" {
  source              = "../../modules/agent-sandbox"
  namespace           = "tenant-b"
  tenant_label        = "tenant-b"
  image               = "${module.ecr.repository_url}:latest"
  keycloak_token_url  = "http://${module.keycloak.service_name}.${module.keycloak.namespace}.svc.cluster.local:8080/realms/ztap/protocol/openid-connect/token"
  gateway_url         = "http://${module.gateway.service_name}.${module.gateway.namespace}.svc.cluster.local:8001/invoke"
  ollama_base_url     = "http://${module.ollama.service_name}.${module.ollama.namespace}.svc.cluster.local:11434/v1/"
  providers = {
    kubernetes = kubernetes
  }
  depends_on = [module.gvisor, module.network_policy, module.keycloak, module.gateway, module.ollama]
}