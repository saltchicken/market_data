import os
import io
import logging
from tqdm import tqdm
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

def init_database(db_url):
    """Executes a SQL file to initialize the database schema."""
    sql_file_path = os.path.join(os.path.dirname(__file__), "sql", "init_schema.sql")

    if not os.path.exists(sql_file_path):
        logger.error(f"SQL file not found at {sql_file_path}")
        return

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            with open(sql_file_path, "r") as file:
                sql_script = file.read()
                conn.execute(text(sql_script))
        logger.info("Successfully initialized database schema.")
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")


def copy_to_sql_with_progress(df, table_name, engine, chunksize=100000):
    """Uses PostgreSQL's native COPY command which is 10-100x faster than standard pandas to_sql."""
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        with tqdm(total=len(df), desc=f"Uploading {table_name}", unit="rows") as pbar:
            for i in range(0, len(df), chunksize):
                chunk = df.iloc[i : i + chunksize]
                buffer = io.StringIO()
                chunk.to_csv(buffer, index=False, header=False, na_rep="\\N")
                buffer.seek(0)

                columns = ",".join([f'"{col}"' for col in chunk.columns])
                sql = f"COPY {table_name} ({columns}) FROM STDIN WITH CSV NULL '\\N'"
                cursor.copy_expert(sql, buffer)

                pbar.update(len(chunk))

        raw_conn.commit()
        cursor.close()
    except Exception as e:
        raw_conn.rollback()
        raise e
    finally:
        raw_conn.close()


def upload_to_postgres(df, table_name, engine):
    """Uploads a pandas DataFrame to a PostgreSQL database."""
    try:
        copy_to_sql_with_progress(df, table_name, engine, chunksize=100000)
    except Exception as e:
        if "UniqueViolation" in str(e) or "duplicate key" in str(e):
            logger.info("Upload Skipped: Data for this date already exists.")
        else:
            logger.error(f"Database Upload Error: {str(e)[:200]}")
