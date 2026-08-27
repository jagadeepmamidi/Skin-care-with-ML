terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "lake_bucket_name" {
  type    = string
  default = "skincare-intelligence-lake"
}

resource "aws_s3_bucket" "lake" {
  bucket = var.lake_bucket_name
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "prefixes" {
  for_each = toset([
    "bronze/",
    "silver/",
    "gold/",
    "quarantine/",
    "_state/",
  ])
  bucket = aws_s3_bucket.lake.id
  key    = each.value
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/skincare-platform/pipeline"
  retention_in_days = 30
}

output "lake_bucket" {
  value = aws_s3_bucket.lake.bucket
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.pipeline.name
}
