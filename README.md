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


EXAMPLE OUTPUT:
$ docker-compose run --rm job
2025-09-05 22:11:24,027 INFO Iniciando proceso ETL
2025-09-05 22:11:25,155 INFO Conteo de registros por tabla: {'chains': 10, 'stores': 400, 'products': 80, 'sellout': 101000}
2025-09-05 22:11:25,520 INFO Eliminados 6334 registros problemáticos. Backup en: sellout_backup_20250905_221125
2025-09-05 22:11:25,533 INFO Conteo final después de curación: {'chains': 10, 'stores': 400, 'products': 80, 'sellout': 94666}
2025-09-05 22:11:26,256 INFO Proceso ETL completado exitosamente

+---------------------------+------------+
| semana                    |   unidades |
|---------------------------+------------|
| 2021-01-18 00:00:00+00:00 |       2634 |
| 2021-01-25 00:00:00+00:00 |       4797 |
| 2021-02-01 00:00:00+00:00 |       4988 |
| 2021-02-08 00:00:00+00:00 |       5049 |
| 2021-02-15 00:00:00+00:00 |       4692 |
| 2021-02-22 00:00:00+00:00 |       4767 |
| 2021-03-01 00:00:00+00:00 |       4699 |
| 2021-03-08 00:00:00+00:00 |       5138 |
| 2021-03-15 00:00:00+00:00 |       4828 |
| 2021-03-22 00:00:00+00:00 |       4492 |
+---------------------------+------------+

2025-09-05 22:11:25,585 INFO Ejecutando consulta 2
2025-09-05 22:11:25,624 INFO 
+---------------------------+------------+
| product_name              |   unidades |
|---------------------------+------------|
| It Annual Nehe            |      13108 |
| Asoka Giant-trumpets      |      12807 |
| Regrant Chee Reedgrass    |      12768 |
| Sub-Ex Coville's Rush     |      12704 |
| Tampflex Splitleaf Cyanea |      12686 |
+---------------------------+------------+

2025-09-05 22:11:25,624 INFO Ejecutando consulta 3
2025-09-05 22:11:26,120 INFO 
+--------------+-------------------------+------------+
| chain_name   | store_name              |   unidades |
|--------------+-------------------------+------------|
| Feedspan     | 8662 Old Shore Crossing |       3091 |
| Aimbu        | 93426 Old Gate Junction |       2843 |
| Ailane       | 91936 Havey Trail       |       2834 |
| Tazzy        | 239 Pond Park           |       2832 |
| Edgeify      | 4 Kings Place           |       2829 |
+--------------+-------------------------+------------+

2025-09-05 22:11:26,120 INFO Ejecutando consulta 4
2025-09-05 22:11:26,256 INFO 
+--------------+--------------+------------+
| chain_name   | dia_semana   |   unidades |
|--------------+--------------+------------|
| Ailane       | Monday       |      16788 |
| Ailane       | Sunday       |      16505 |
| Ailane       | Saturday     |      16062 |
| Ailane       | Thursday     |      15957 |
| Ailane       | Wednesday    |      15833 |
| Ailane       | Tuesday      |      14965 |
| Ailane       | Friday       |      14810 |
| Aimbu        | Sunday       |      15883 |
| Aimbu        | Saturday     |      15876 |
| Aimbu        | Wednesday    |      15325 |
+--------------+--------------+------------+

## 🚀 AWS (conceptual, Free Tier)

### A. Diagrama (alto nivel)

```text
        +------------------+
        |      ETL Job     |
        |  (Docker/Python) |
        +--------+---------+
                 |
                 v
        +--------+---------+
        |  RDS PostgreSQL  |
        | db.t4g.micro     |
        +--------+---------+
                 |
    +------------+-------------+
    |                          |
    v                          v
+---+---+                +-----+------+
| S3     |                | CloudWatch |
| Backups |                |   Logs     |
+---+---+                +-----+------+

Notas de configuración

RDS: db.t4g.micro (free tier), almacenamiento ≤20 GB, 1 AZ, backups automáticos habilitados, acceso por puerto 5432 (Security Group).

S3: bucket etl-backup-ludagoju, cifrado por defecto (AES-256), regla de lifecycle para eliminar backups a los 30 días.

CloudWatch Logs: exportar logs de RDS al grupo rds/postgresql, retención máxima 7 días.

IAM: usuario/rol con política de mínimo privilegio: solo s3:PutObject en el prefijo /backups/ del bucket.

Free Tier: mantenerse dentro del límite usando una instancia chica (db.t4g.micro), pocos GB en disco y retención corta de logs/backups.

Guía breve (alto nivel)

Crear instancia RDS PostgreSQL (db.t4g.micro, 20 GB, backups automáticos, acceso público limitado).

Crear bucket S3 con cifrado habilitado y lifecycle de 30 días.

Definir usuario/rol IAM con permisos mínimos para subir backups (s3:PutObject → bucket/backups/).

Configurar CloudWatch Logs para exportar logs de RDS con retención de 7 días.

Ejecutar el job ETL (Docker/Python) apuntando a la RDS.

Validar:

Logs de RDS en CloudWatch.

Backups comprimidos en S3.

Consultas y KPIs corriendo sobre la RDS.