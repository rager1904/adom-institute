output "instance_public_ip" {
  description = "Public IP of the ADOM app node (empty until `terraform refresh`)"
  value       = oci_core_instance.app_node1.public_ip
}

output "instance_ocid" {
  value = oci_core_instance.app_node1.id
}

output "object_storage_namespace" {
  description = "Used to build the S3-compatible endpoint: https://<namespace>.compat.objectstorage.<region>.oraclecloud.com"
  value       = data.oci_objectstorage_namespace.tenant.namespace
}

output "region" {
  value = var.region
}

output "media_bucket" {
  value = oci_objectstorage_bucket.media.name
}

output "backups_bucket" {
  value = oci_objectstorage_bucket.backups.name
}