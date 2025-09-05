#!/bin/bash
set -e

export PGPASSWORD=$POSTGRES_PASSWORD

# Variables de entorno
DB_HOST=${POSTGRES_HOST:-db}
DB_NAME=${POSTGRES_DB}
DB_USER=${POSTGRES_USER}
BUCKET_NAME=${S3_BUCKET}

# Crear carpeta temporal si no existe
mkdir -p /app/tmp

FILE=/app/tmp/backup_$(date +%Y%m%d_%H%M%S).sql.gz

echo "Generando backup..."
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME | gzip > $FILE

echo "Subiendo a S3: s3://$BUCKET_NAME/"
aws s3 cp $FILE s3://$BUCKET_NAME/

echo "✅ Backup completado!"
