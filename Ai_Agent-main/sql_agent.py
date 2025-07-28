import openai
import logging
import re
import json
from functools import lru_cache
from decimal import Decimal
from datetime import datetime
from database import Database
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd
import base64
import tempfile
import os
import matplotlib


matplotlib.use('Agg')  # Important : désactive le backend GUI de tkinter
import matplotlib.pyplot as plt


logger = logging.getLogger(__name__)

class SQLAgent:
    def _serialize_data(self, data):
        if isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {key: self._serialize_data(value) for key, value in data.items()}
        elif hasattr(data, 'isoformat'):
            return data.isoformat()
        elif isinstance(data, Decimal):
            return float(data)
        return data

    def __init__(self):
        self.db = Database()
        self.schema = self.db.get_schema_info()
        self.last_generated_sql = None
        self.query_history = []
        self.model = "gpt-3.5-turbo"
        self.temperature = 0.3
        self.max_tokens = 1000

    def load_prompt_for_query(self, query):
        if any(word in query.lower() for word in ["nom", "élève", "classe", "parent", "inscription"]):
            path = "prompt_eleve.txt"
            extra_info = ""
        elif any(word in query.lower() for word in ["note", "matière", "absence", "emploi", "moyenne"]):
            path = "prompt_pedagogie.txt"
            # Injection du texte des relations FK dans le prompt pédagogique
            try:
                extra_info = "\n\n" + self.db.get_simplified_relations_text()
            except Exception as e:
                logger.error(f"Erreur récupération relations FK : {e}")
                extra_info = ""
        elif any(word in query.lower() for word in ["paiement", "tranche", "cantine", "montant", "transport"]):
            path = "prompt_finance.txt"
            extra_info = ""
        else:
            path = "prompt_eleve.txt"
            extra_info = ""

        try:
            with open(path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            return prompt + extra_info
        except Exception as e:
            logger.error(f"Erreur chargement prompt: {e}")
            raise
    def detect_graph_type(user_query):
        user_query = user_query.lower()
        if any(k in user_query for k in ["pie", "camembert", "diagramme circulaire"]):
            return "pie"
        elif any(k in user_query for k in ["histogramme", "bar chart", "barres"]):
            return "bar"
        elif any(k in user_query for k in ["ligne", "line chart", "courbe"]):
            return "line"
        else:
            return None



    def generate_sql(self, natural_query):
        try:
            prompt = self.load_prompt_for_query(natural_query)
            prompt += f"\n### Question:\n{natural_query}\n### Format:\nRetournez uniquement la requête SQL sans commentaire ni explication."
            messages = [{"role": "system", "content": prompt}]
            print("Clé OpenAI utilisée :", openai.api_key)

            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            sql = self._extract_sql(response.choices[0].message.content)
            if not self._validate_sql(sql):
                raise ValueError("Validation SQL échouée")
            self.last_generated_sql = sql
            self.query_history.append({
                'query': natural_query,
                'sql': sql,
                'timestamp': datetime.now()
            })
            return sql
        except Exception as e:
            logger.error(f"Erreur génération SQL: {str(e)}")
            raise

    def _extract_sql(self, text):
        sql = re.sub(r'(?i)^\s*(?:--|#).*$', '', text, flags=re.MULTILINE)
        sql = re.sub(r'(?:sql)?\s*([^`]+)', r'\1', text, flags=re.DOTALL)
        return sql.strip().rstrip(';')
    def _strip_db_prefix(self, table_name):
        return table_name.split('.')[-1]  # garde uniquement le nom de la table

    def _validate_sql(self, sql):
        sql_lower = sql.lower()
        forbidden = ['drop', 'delete', 'update', 'insert', ';--', 'exec']
        if any(cmd in sql_lower for cmd in forbidden):
            raise ValueError("Commande SQL dangereuse détectée")
        if not re.match(r'^\s*select\s+', sql_lower):
            raise ValueError("Seules les requêtes SELECT sont autorisées")

        # Extraire les noms de tables après FROM et JOIN
        used_tables = set(re.findall(r'\bfrom\s+([a-zA-Z0-9_.]+)|\bjoin\s+([a-zA-Z0-9_.]+)', sql_lower))
        for table in (t for group in used_tables for t in group if t):
            clean_table = self._strip_db_prefix(table)
            if clean_table not in self.schema:
                raise ValueError(f"Table inconnue: {table}")
        return True
    


    def execute_natural_query(self, natural_query):
        try:
            sql = self.generate_sql(natural_query)
            result = self.db.execute_query(sql)
            if not result['success']:
                corrected = self._auto_correct(sql, result['error'])
                if corrected:
                    result = self.db.execute_query(corrected)
                    if result['success']:
                        return self._format_results(result['data'], user_query=natural_query)
                raise ValueError(f"Erreur SQL: {result['error']}")
            return self._format_results(result['data'], user_query=natural_query)
        except Exception as e:
            logger.error(f"Erreur exécution: {str(e)}")
            raise

    def _auto_correct(self, bad_sql, error_msg):
        try:
            correction_prompt = f"""
Corrige cette requête SQL:
Requête: {bad_sql}
Erreur: {error_msg}
Schéma disponible:
{json.dumps(self.schema, indent=2)}
"""
            response = openai.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": correction_prompt}],
                temperature=0,
                max_tokens=500
            )
            corrected_sql = self._extract_sql(response.choices[0].message.content)
            if self._validate_sql(corrected_sql):
                return corrected_sql
        except Exception as e:
            logger.error(f"Correction échouée: {str(e)}")
        return None
    
    def detect_graph_type(self, user_query):
        user_query = user_query.lower()
        if any(k in user_query for k in ["pie", "camembert", "diagramme circulaire"]):
            return "pie"
        elif any(k in user_query for k in ["histogramme", "bar chart", "barres"]):
            return "bar"
        elif any(k in user_query for k in ["ligne", "line chart", "courbe"]):
            return "line"
        else:
            return None
    import re

    def extract_name_from_query(query):
        # Exemple basique pour capturer : "attestation de Rania Zahraoui"
        pattern = r"attestation de\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)*)"
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def get_student_info_by_name(self, full_name):
        """Récupère les infos d'un élève à partir de son nom complet"""
        try:
            # Requête principale
            sql = """
            SELECT 
                ei.NomPrenomFr AS nom,
                e.DateNaissance AS date_naissance,
                IFNULL(e.LieuNaissance, e.AutreLieuNaissance) AS lieu_de_naissance,
                ei.nomclassefr AS classe,
                e.IdPersonne AS matricule
            FROM 
                eleveinscri ei
            JOIN 
                eleve e ON ei.NomPrenomFr = %s
            WHERE 
                ei.NomPrenomFr = %s
            LIMIT 1;
            """

            # Exécution de la requête avec double paramètre pour correspondance stricte
            result = self.db.execute_query(sql, (full_name, full_name))

            if not result['success'] or not result['data']:
                return None  # Aucun résultat trouvé

            return result['data'][0]

        except Exception as e:
            logger.error(f"Erreur get_student_info_by_name: {str(e)}")
            return None




    def generate_auto_graph(self, df, graph_type=None):
        if df.empty:
            return "Aucun résultat à afficher."

        exclude_cols = ['id', 'ids', 'anneescolaire', 'année scolaire', 'annee_scolaire']
        numeric_cols = [col for col in df.select_dtypes(include='number').columns if col.lower() not in exclude_cols]
        categorical_cols = [col for col in df.select_dtypes(exclude='number').columns if col.lower() not in exclude_cols]

        if not numeric_cols or not categorical_cols:
            return df.to_markdown()

        x_col = categorical_cols[0]
        y_cols = numeric_cols

        if graph_type == "pie":
            df_grouped = df.groupby(x_col)[y_cols[0]].sum()
            plt.figure(figsize=(6, 6))
            df_grouped.plot(kind='pie', autopct='%1.1f%%', ylabel='', legend=False)
            plt.title(f"{y_cols[0]} par {x_col}")
            plt.tight_layout()

        elif graph_type == "line":
            print("Colonnes catégorielles:", categorical_cols)
            print("Colonnes numériques:", numeric_cols)
            print("x_col choisi:", x_col)

            order = ["1ère", "2ème", "3ème", "4ème", "5ème", "6ème", "7ème", "8ème", "9ème"]

            if 'niveau' in x_col.lower():
                df_sorted = df.copy()
                df_sorted[x_col] = df_sorted[x_col].str.strip().str.replace(" ", "").str.lower()
                order_clean = [x.lower() for x in order]
                df_sorted[x_col] = pd.Categorical(df_sorted[x_col], categories=order_clean, ordered=True)
                df_sorted = df_sorted.sort_values(x_col)
            elif 'date' in x_col.lower() or 'année' in x_col.lower():
                df_sorted = df.sort_values(x_col)
            else:
                df_sorted = df

            plt.figure(figsize=(10, 6))
            plt.plot(df_sorted[x_col], df_sorted[y_cols[0]], marker='o')
            plt.title(f"Évolution de {y_cols[0]} selon {x_col}")
            plt.xlabel(x_col)
            plt.ylabel(y_cols[0])
            plt.xticks(rotation=45)
            plt.tight_layout()

        elif graph_type == "bar":
            plt.figure(figsize=(10, 6))
            df.plot(x=x_col, y=y_cols, kind='bar')
            plt.title(f"{', '.join(y_cols)} par {x_col}")
            plt.xticks(rotation=45)
            plt.tight_layout()

        else:
            # Logique par défaut si aucun type précisé
            if len(y_cols) == 1 and df[x_col].nunique() <= 7:
                df_grouped = df.groupby(x_col)[y_cols[0]].sum()
                plt.figure(figsize=(6, 6))
                df_grouped.plot(kind='pie', autopct='%1.1f%%', ylabel='', legend=False)
                plt.title(f"{y_cols[0]} par {x_col}")
            elif 'date' in x_col.lower() or 'année' in x_col.lower() or pd.to_datetime(df[x_col], errors='coerce').notna().all():
                df_sorted = df.sort_values(x_col)
                plt.figure(figsize=(10, 6))
                df_sorted.plot(x=x_col, y=y_cols, kind='line', marker='o')
                plt.title(f"Évolution de {', '.join(y_cols)} selon {x_col}")
            else:
                plt.figure(figsize=(10, 6))
                df.plot(x=x_col, y=y_cols, kind='bar')
                plt.title(f"{', '.join(y_cols)} par {x_col}")

            plt.xticks(rotation=45)
            plt.tight_layout()

        # Générer le graphique en base64
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        tmp_path = tmpfile.name
        tmpfile.close()
        plt.savefig(tmp_path)
        plt.close()

        with open(tmp_path, 'rb') as f:
            img_bytes = f.read()
        encoded = base64.b64encode(img_bytes).decode('utf-8')

        return f"![Graphique](data:image/png;base64,{encoded})"




    def _format_results(self, data, user_query=None):
        serialized_data = self._serialize_data(data)
        if not serialized_data:
            return "Aucun résultat trouvé."

        df = pd.DataFrame(serialized_data)

        # Détection du type de graphique demandé dans la requête utilisateur
        graph_type = None
        if user_query:
            graph_type = self.detect_graph_type(user_query)

        # Logique existante avec passage de graph_type
        if (len(df.columns) >= 2 and 
            any('niveau' in col.lower() for col in df.columns) and 
            any('inscription' in col.lower() for col in df.columns)):
            return self.generate_auto_graph(df, graph_type=graph_type)
        
        if df.empty:
            return "Aucun résultat trouvé."

        if len(df) > 10 or len(df.select_dtypes(include='number').columns) > 1:
            return self.generate_auto_graph(df, graph_type=graph_type)

        return tabulate(df, headers='keys', tablefmt='github')
