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
  source       = "../../modules/node-group"
  cluster_name = module.eks_cluster.cluster_name
  subnet_ids   = module.vpc.subnet_ids
  instance_type = var.node_instance_type
  capacity_type = var.node_capacity_type
}

module "cilium" {
  source            = "../../modules/cilium"
  cluster_name      = module.eks_cluster.cluster_name
  tenant_namespaces = ["tenant-a", "tenant-b"]
  providers = {
    helm       = helm
    kubernetes = kubernetes
  }
  depends_on = [module.node_group]
}
