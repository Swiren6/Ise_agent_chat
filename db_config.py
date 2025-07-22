from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv
import os
import mysql.connector

load_dotenv()

def get_mysql_config():
    """Retourne la configuration MySQL sous forme de dictionnaire"""
    return {
        'host': os.getenv('MYSQL_HOST'),
        'port': int(os.getenv('MYSQL_PORT', '3306')),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE')
    }

def get_db_connection():
    """Retourne une connexion SQLDatabase configurée"""
    config = get_mysql_config()
    
    # Test de connexion
    try:
        conn = mysql.connector.connect(**config)
        print("✅ Connexion MySQL réussie.")
        conn.close()
    except Exception as e:
        print(f"❌ ERREUR de connexion MySQL: {e}")
        exit(1)

    return SQLDatabase.from_uri(
        f"mysql+mysqlconnector://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}",
        sample_rows_in_table_info=0,
        engine_args={"pool_timeout": 30, "pool_recycle": 3600}
    )