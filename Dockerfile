FROM python:3.11-slim
# imagen base de Python ligera

WORKDIR /app
# definimos /app como la carpeta principal

COPY . /app
# copiamos el contenido del proyecto a la carpeta /app

RUN pip install psycopg2-binary pandas
# instalamos librerias necesarias para conectar PostgreSQL y manejar datos

RUN pip install tabulate

# Instalar clientes necesarios
RUN apt-get update && apt-get install -y postgresql-client awscli && rm -rf /var/lib/apt/lists/*

COPY src/ /app/src
COPY sql/ /app/sql

CMD ["python", "src/job.py"]
# al iniciar el contenedor, se ejecuta el script job.py 


