# ---------------------------------------------------------------------------
# ADOM Institute - OCI Always Free / PAYG stack
#
# Creates:
#   1 x VM.Standard.A1.Flex (Arm)   - default 2 OCPU / 12 GB (Always Free 2026)
#   1 x 100 GB block volume         - PostgreSQL data (fits the 200 GB free allotment)
#   1 x VCN 10.0.0.0/16 + public subnet + Internet gateway + security list
#   2 x Object Storage buckets      - adom-media (media/static), adom-backups
#
# Always Free note (June 2026): the free Ampere allowance is 2 OCPU + 12 GB
# in total. Upgrade the tenancy to Pay-As-You-Go to keep those resources free
# forever AND unlock the older 4 OCPU / 24 GB allowance for this instance.
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.30"
    }
  }
}

# ---------------------------------------------------------------------------
provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# Latest Canonical Ubuntu (aarch64) image for the A1 shape.
# If this returns empty, paste an image OCID into app_image_id.
data "oci_core_images" "ubuntu_aarch64" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  state                    = "AVAILABLE"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

locals {
  ad_name            = var.availability_domain != "" ? var.availability_domain : data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_index].name
  app_image_id       = var.app_image_id != "" ? var.app_image_id : data.oci_core_images.ubuntu_aarch64.images[0].id
  media_bucket_name  = "${var.bucket_prefix}-media"
  backups_bucket     = "${var.bucket_prefix}-backups"
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
resource "oci_core_vcn" "adom" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "adom-vcn"
  dns_label      = "adomvcn"
}

resource "oci_core_internet_gateway" "adom" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.adom.id
  display_name   = "adom-igw"
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.adom.id
  display_name   = "adom-public-rt"
  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.adom.id
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.adom.id
  display_name   = "adom-public-sl"

  ingress_security_rules {
    description = "HTTPS"
    protocol    = "6"
    source      = "0.0.0.0/0"
    tcp_options {
      max = 443
      min = 443
    }
  }
  ingress_security_rules {
    description = "HTTP"
    protocol    = "6"
    source      = "0.0.0.0/0"
    tcp_options {
      max = 80
      min = 80
    }
  }
  # Harden afterwards: replace 0.0.0.0/0 with your office/public IP CIDR.
  ingress_security_rules {
    description = "SSH"
    protocol    = "6"
    source      = var.ssh_ingress_cidr
    tcp_options {
      max = 22
      min = 22
    }
  }
  egress_security_rules {
    description = "All egress"
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

resource "oci_core_subnet" "public" {
  compartment_id      = var.compartment_ocid
  vcn_id              = oci_core_vcn.adom.id
  cidr_block          = "10.0.1.0/24"
  display_name        = "adom-public-subnet"
  dns_label           = "adompub"
  security_list_ids   = [oci_core_security_list.public.id]
  route_table_id      = oci_core_route_table.public.id
  prohibit_public_ip_on_vnic = false
}

# ---------------------------------------------------------------------------
# Compute - ADOM app node
# ---------------------------------------------------------------------------
resource "oci_core_instance" "app_node1" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = "adom-app-1"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gbs
  }

  source_details {
    source_type = "image"
    source_id   = local.app_image_id
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    display_name     = "adom-app-1-vnic"
    hostname_label   = "adom-app-1"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(file("${path.module}/cloud-init/app-node.sh"))
  }

  preserve_boot_volume = false
}

# ---------------------------------------------------------------------------
# PostgreSQL block volume (100 GB - leaves headroom in the 200 GB free pool)
# ---------------------------------------------------------------------------
resource "oci_core_volume" "pg_data" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = "adom-pg-data"
  size_in_gbs         = var.block_volume_size_gb
}

resource "oci_core_volume_attachment" "pg_data" {
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.app_node1.id
  volume_id       = oci_core_volume.pg_data.id
  display_name    = "adom-pg-data-attach"
}

# ---------------------------------------------------------------------------
# Object Storage
# ---------------------------------------------------------------------------
data "oci_objectstorage_namespace" "tenant" {
  compartment_id = var.compartment_ocid
}

resource "oci_objectstorage_bucket" "media" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.tenant.namespace
  name           = local.media_bucket_name
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
}

resource "oci_objectstorage_bucket" "backups" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.tenant.namespace
  name           = local.backups_bucket
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
}