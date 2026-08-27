# Optional AWS cutover (local-first remains MinIO + DuckDB).
#
# Local                 Cloud
# -----                 -----
# MinIO            →    S3 (this Terraform)
# DuckDB/Postgres  →    RDS PostgreSQL or Athena over S3
# Airflow logs     →    CloudWatch log group
# Spark local      →    Glue jobs (same silver scripts)
#
# Do not apply this stack until the local batch pipeline is green.
