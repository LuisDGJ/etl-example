# src/job.py
import os
import logging
import psycopg2
from datetime import datetime
from tabulate import tabulate
from psycopg2 import sql, errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Archivos SQL de arranque (se ejecutan en este orden)
STARTUP_SQL_FILES = [
    "ddl/chains.sql",
    "ddl/stores.sql",
    "ddl/products.sql",
    "ddl/combined_sellout.sql"
]

# Tablas que queremos inspeccionar después de cargar
EXPECTED_TABLE_NAMES = ["chains", "stores", "products", "sellout"]

# Posibles nombres de la columna de cantidad para buscar automáticamente
QUANTITY_COLUMN_CANDIDATES = ["quantity", "qty", "cantidad", "amount"]

class ETLException(Exception):
    """Excepción personalizada para errores del ETL"""
    pass

def get_conn():
    """Establece conexión a la base de datos con manejo de errores"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "db"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "etl_db"),
            user=os.getenv("POSTGRES_USER", "etl_user"),
            password=os.getenv("POSTGRES_PASSWORD", "etl_pass"),
            connect_timeout=10
        )
        conn.autocommit = False  # Desactivar autocommit para manejar transacciones manualmente
        return conn
    except psycopg2.OperationalError as e:
        logging.error("Error de conexión a la base de datos: %s", e)
        raise ETLException(f"No se pudo conectar a la base de datos: {e}")

def execute_sql_file(conn, path):
    """Ejecuta un archivo SQL con manejo robusto de errores y transacciones"""
    logging.info("Ejecutando SQL: %s", path)
    
    if not os.path.exists(path):
        logging.error("Archivo no encontrado: %s", path)
        return False
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        if not content:
            logging.warning("Archivo SQL vacío: %s", path)
            return True
            
        with conn.cursor() as cur:
            # Intentar ejecutar todo el contenido primero
            try:
                cur.execute(content)
                conn.commit()
                logging.info("Ejecutado exitosamente (single execute): %s", path)
                return True
            except (errors.SyntaxError, errors.UndefinedTable, errors.DuplicateTable) as e:
                logging.warning("No se pudo ejecutar de una sola vez (%s). Dividiendo en sentencias.", e)
                conn.rollback()
                
                # Dividir en sentencias individuales
                statements = [s.strip() for s in content.split(';') if s.strip()]
                success_count = 0
                
                for stmt in statements:
                    try:
                        if stmt:  # Ignorar statements vacíos
                            cur.execute(stmt)
                            success_count += 1
                    except (errors.DuplicateTable, errors.DuplicateObject) as e:
                        logging.warning("Sentencia duplicada (se omite): %s - %s", stmt[:100], e)
                        conn.rollback()
                    except Exception as e:
                        logging.error("Error ejecutando sentencia: %s - %s", stmt[:100], e)
                        conn.rollback()
                        raise ETLException(f"Error en sentencia SQL: {e}")
                
                conn.commit()
                logging.info("Ejecutado (por sentencias): %s. %d/%d sentencias exitosas.", 
                           path, success_count, len(statements))
                return success_count == len(statements)
                
    except Exception as e:
        logging.error("Error inesperado procesando archivo %s: %s", path, e)
        conn.rollback()
        return False

def get_existing_table(conn, candidates):
    """Verifica si existe alguna de las tablas candidatas"""
    with conn.cursor() as cur:
        for table_name in candidates:
            try:
                cur.execute("SELECT to_regclass(%s);", (table_name,))
                result = cur.fetchone()[0]
                if result:
                    return table_name
            except Exception as e:
                logging.warning("Error verificando tabla %s: %s", table_name, e)
                continue
    return None

def count_tables(conn, table_names):
    """Cuenta registros en tablas existentes"""
    found = {}
    with conn.cursor() as cur:
        for table_name in table_names:
            try:
                cur.execute("SELECT to_regclass(%s);", (table_name,))
                if cur.fetchone()[0]:
                    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
                    found[table_name] = cur.fetchone()[0]
                else:
                    found[table_name] = "No existe"
            except Exception as e:
                logging.error("Error contando tabla %s: %s", table_name, e)
                found[table_name] = f"Error: {e}"
    return found

def detect_quantity_column(conn, table_name):
    """Detecta automáticamente la columna de cantidad"""
    with conn.cursor() as cur:
        try:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND data_type IN ('integer', 'numeric', 'double precision', 'real')
            """, (table_name,))
            
            numeric_columns = [row[0] for row in cur.fetchall()]
            
            # Buscar coincidencias primero
            for candidate in QUANTITY_COLUMN_CANDIDATES:
                if candidate in numeric_columns:
                    return candidate
            
            # Si no encuentra, usar la primera columna numérica
            if numeric_columns:
                logging.info("Usando columna numérica detectada: %s", numeric_columns[0])
                return numeric_columns[0]
                
        except Exception as e:
            logging.error("Error detectando columna de cantidad: %s", e)
            
    return None

def perform_curation(conn):
    """Realiza procesos de limpieza y transformación de datos"""
    logging.info("Iniciando curación de datos")
    
    # Detectar tabla de sellout
    sellout_table = get_existing_table(conn, ["combined_sellout", "sales", "sellout"])
    if not sellout_table:
        logging.warning("No se encontró tabla de sellout. Saltando curación.")
        return False
    
    logging.info("Tabla de sellout detectada: %s", sellout_table)
    
    try:
        # 1) Convertir daily a DATE si existe
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'daily'
            """, (sellout_table,))
            
            daily_col = cur.fetchone()
            if daily_col:
                col_name, data_type = daily_col
                if data_type != 'date':
                    logging.info("Convirtiendo columna daily a DATE")
                    try:
                        cur.execute(sql.SQL("ALTER TABLE {} ALTER COLUMN daily TYPE DATE USING daily::date").format(
                            sql.Identifier(sellout_table)))
                        conn.commit()
                        logging.info("Conversión exitosa de daily a DATE")
                    except Exception as e:
                        logging.warning("No se pudo convertir daily directamente: %s", e)
                        conn.rollback()
                        # Intentar método alternativo
                        try:
                            cur.execute(sql.SQL("""
                                ALTER TABLE {} ADD COLUMN daily_temp DATE;
                                UPDATE {} SET daily_temp = CASE 
                                    WHEN daily ~ '^\d{4}-\d{2}-\d{2}$' THEN daily::date
                                    ELSE NULL END;
                                ALTER TABLE {} DROP COLUMN daily;
                                ALTER TABLE {} RENAME COLUMN daily_temp TO daily;
                            """).format(
                                sql.Identifier(sellout_table),
                                sql.Identifier(sellout_table),
                                sql.Identifier(sellout_table),
                                sql.Identifier(sellout_table)))
                            conn.commit()
                            logging.info("Conversión alternativa exitosa")
                        except Exception as e2:
                            logging.error("Error en conversión alternativa: %s", e2)
                            conn.rollback()
            
        # 2) Validar y limpiar datos de cantidad
        quantity_col = detect_quantity_column(conn, sellout_table)
        if not quantity_col:
            logging.warning("No se detectó columna de cantidad en %s", sellout_table)
            return True
            
        logging.info("Columna de cantidad detectada: %s", quantity_col)
        
        with conn.cursor() as cur:
            # Contar registros problemáticos
            cur.execute(sql.SQL("""
                SELECT COUNT(*) FROM {} 
                WHERE {} IS NULL OR {} <= 0 OR {} > 1000000
            """).format(
                sql.Identifier(sellout_table),
                sql.Identifier(quantity_col),
                sql.Identifier(quantity_col),
                sql.Identifier(quantity_col)))
            
            problematic_records = cur.fetchone()[0]
            logging.info("Registros problemáticos detectados: %d", problematic_records)
            
            if problematic_records > 0:
                # Crear backup antes de eliminar
                backup_table = f"{sellout_table}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                cur.execute(sql.SQL("CREATE TABLE {} AS SELECT * FROM {}").format(
                    sql.Identifier(backup_table),
                    sql.Identifier(sellout_table)))
                
                # Eliminar registros problemáticos
                cur.execute(sql.SQL("DELETE FROM {} WHERE {} IS NULL OR {} <= 0 OR {} > 1000000").format(
                    sql.Identifier(sellout_table),
                    sql.Identifier(quantity_col),
                    sql.Identifier(quantity_col),
                    sql.Identifier(quantity_col)))
                
                conn.commit()
                logging.info("Eliminados %d registros problemáticos. Backup en: %s", 
                           problematic_records, backup_table)
        
        return True
        
    except Exception as e:
        logging.error("Error en proceso de curación: %s", e)
        conn.rollback()
        return False

def ejecutar_consultas(cursor, conn):
    logging.info("Ejecutando consultas de validación desde sql/queries.sql")

    with open("sql/queries.sql", "r") as f:
        contenido = f.read()

    consultas = [q.strip() for q in contenido.split(";") if q.strip()]

    for i, consulta in enumerate(consultas, start=1):
        try:
            logging.info(f"Ejecutando consulta {i}")
            cursor.execute(consulta)
            resultados = cursor.fetchall()

            # Obtener nombres de columnas
            colnames = [desc[0] for desc in cursor.description]

            # Formato tabular
            tabla = tabulate(resultados[:10], headers=colnames, tablefmt="psql")
            logging.info(f"\n{tabla}\n")

        except Exception as e:
            logging.error(f"Error ejecutando consulta {i}: {e}")
            conn.rollback()


def main():
    """Función principal con manejo robusto de errores"""
    logging.info("Iniciando proceso ETL")
    conn = None
    
    try:
        # Establecer conexión
        conn = get_conn()
        
        # Ejecutar scripts SQL
        for sql_file in STARTUP_SQL_FILES:
            if not execute_sql_file(conn, sql_file):
                logging.error("Error crítico ejecutando %s. Abortando.", sql_file)
                raise ETLException(f"Error ejecutando {sql_file}")
        
        # Verificar resultados
        counts = count_tables(conn, EXPECTED_TABLE_NAMES)
        logging.info("Conteo de registros por tabla: %s", counts)
        
        # Realizar curación de datos
        if not perform_curation(conn):
            logging.warning("Proceso de curación encontró problemas")
        
        # Verificación final
        final_counts = count_tables(conn, EXPECTED_TABLE_NAMES)
        logging.info("Conteo final después de curación: %s", final_counts)
        
        with conn.cursor() as cursor:
            ejecutar_consultas(cursor, conn)

        logging.info("Proceso ETL completado exitosamente")
        
    except ETLException as e:
        logging.error("Error en proceso ETL: %s", e)
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logging.error("Error inesperado: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
            logging.info("Conexión a BD cerrada")

if __name__ == "__main__":
    main()