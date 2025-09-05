# ETL Docker AWS

Este proyecto implementa un pipeline ETL en Python y PostgreSQL usando Docker, con opción de despliegue en AWS.

Quickstart — ETL con Docker + PostgreSQL (requisitos: Docker + docker-compose).
1. Clona el repo y entra: `git clone https://github.com/LuisDGJ/etl-example.git && cd etl-docker-aws`
2. Crea .env desde el ejemplo: `cp .env.example .env` y ajusta POSTGRES_* y S3_BUCKET/AWS_* según corresponda.
3. Levantar la base de datos local: `docker compose up -d db`
4. Ejecutar el job ETL (una sola ejecución): `docker compose run --rm job`
5. Validar en la BD (local): `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM products;"`
6. Si usas RDS: configure POSTGRES_HOST/PORT en `.env` y ejecute `docker compose run --rm job` apuntando a RDS.
7. Los logs en consola muestran inicio/fin, filas procesadas, KPIs y resumen estacional.
8. Supuestos: los DDL/INSERT están en `ddl/`, queries en `sql/queries.sql`, y AWS CLI configured para backups.
9. Limitaciones: diseñado para demo/datasets pequeños; no exponer 5432 públicamente.
10. Para backups: `scripts/backup.sh` usa pg_dump + gzip + aws s3 cp (requiere credenciales).
