variable "tenancy_ocid" {
  description = "OCI tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI API user OCID"
  type        = string
}

variable "fingerprint" {
  description = "OCI API key fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API signing private key (PEM)"
  type        = string
}

variable "region" {
  description = "OCI region (e.g. us-ashburn-1). Must match the tenancy home region to stay Always Free."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment (defaults to the tenancy/root compartment)"
  type        = string
  default     = ""
}

variable "ssh_public_key" {
  description = "Contents of your SSH public key for the VM"
  type        = string
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to SSH to the VM. Harden to your office/public IP, e.g. 196.0.0.1/32 (defaults to 0.0.0.0/0 for bootstrap)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "availability_domain" {
  description = "Availability Domain name (leave empty to use availability_domain_index)"
  type        = string
  default     = ""
}

variable "availability_domain_index" {
  description = "Index into the region's availability domain list"
  type        = number
  default     = 0
}

variable "instance_ocpus" {
  description = "Ampere A1 OCPUs for the app node (Always Free 2026: 2 total across tenancy)"
  type        = number
  default     = 2
}

variable "instance_memory_gbs" {
  description = "Ampere A1 memory in GB (Always Free 2026: 12 total across tenancy)"
  type        = number
  default     = 12
}

variable "block_volume_size_gb" {
  description = "Block volume for PostgreSQL data (free pool: 200 GB combined boot+block, home region only)"
  type        = number
  default     = 100
}

variable "app_image_id" {
  description = "Optional explicit image OCID for VM.Standard.A1.Flex (fallback if the Ubuntu image lookup returns empty)"
  type        = string
  default     = ""
}

variable "bucket_prefix" {
  description = "Prefix for object storage buckets (must be unique within the namespace)"
  type        = string
  default     = "adom"
}