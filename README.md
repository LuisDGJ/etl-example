# ETL Docker AWS

Este proyecto implementa un pipeline ETL en Python y PostgreSQL usando Docker, con opción de despliegue en AWS.

## Pasos de uso
1. Clonar el repositorio.
2. Copiar `.env.example` a `.env` y ajustar valores.
3. Levantar la base de datos: `docker-compose up -d db`.
4. Correr el job ETL: `docker-compose run job`.
5. Consultar los KPIs cargados en logs.
6. Para backups: usar `scripts/backup.sh` (requiere AWS CLI configurado).
7. Arquitectura mínima soporta RDS (free tier) y S3 (backups 30d).
8. Logs de ejecución visibles en consola; en AWS se exportan a CloudWatch.
9. Repositorio es portable: local (Docker) o remoto (AWS RDS/S3).
10. Ideal para prácticas de ETL y despliegue reproducible.