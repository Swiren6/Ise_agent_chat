import mysql.connector
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.config = {
            "host": "127.0.0.1",  # Connexion via TCP/IP
            "user": "root",
            "password": "12345",
            "database": "bd_eduise2"
        }

    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.config)
            conn.ping(reconnect=True)
            logger.info("[🔗] Connexion à la base de données établie.")
            return conn
        except mysql.connector.Error as err:
            logger.error(f"[❌] Erreur MySQL: {err}")
            raise

    def execute_query(self, query, params=None, fetch=True):
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            logger.info(f"[SQL EXECUTE] Requête exécutée:\n{query}")
            if params:
                logger.info(f"[SQL PARAMS] Paramètres: {params}")
            
            cursor.execute(query, params or ())
            if fetch:
                results = cursor.fetchall()
                conn.commit()
                logger.info(f"[SQL RESULT] {len(results)} lignes retournées")
                return {'success': True, 'data': results}
            conn.commit()
            return {'success': True}
        except Exception as e:
            logger.error(f"[SQL ERROR] Erreur d'exécution: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            cursor.close()
            conn.close()

    def get_schema_info(self):
        schema = {}
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()

            for table in tables:
                table_name = table[f"Tables_in_{self.config['database']}"]
                cursor.execute(f"DESCRIBE {table_name}")
                schema[table_name] = cursor.fetchall()
                
            return schema
        finally:
            cursor.close()
            conn.close()

    def get_foreign_key_relations(self):
        query = """
            SELECT 
                TABLE_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM 
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE 
                TABLE_SCHEMA = %s 
                AND REFERENCED_TABLE_NAME IS NOT NULL;
        """
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, (self.config["database"],))
            results = cursor.fetchall()
            return results
        finally:
            cursor.close()
            conn.close()

    def get_simplified_relations_text(self):
        fk_relations = self.get_foreign_key_relations()
        simplified = {}
        for row in fk_relations:
            table = row['TABLE_NAME']
            referenced_table = row['REFERENCED_TABLE_NAME']
            if table not in simplified:
                simplified[table] = set()
            simplified[table].add(referenced_table)

        lines = ["Relations clés principales entre tables :\n"]
        for table, references in simplified.items():
            line = f"- {table} liée à " + ", ".join(sorted(references)) + "."
            lines.append(line)
        return "\n".join(lines)
