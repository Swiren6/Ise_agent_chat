import openai
import os
import logging
import json
import tiktoken
from sql_agent import SQLAgent
from dotenv import load_dotenv


load_dotenv()  # charge les variables d'environnement depuis .env

openai.api_key = os.getenv("OPENAI_API_KEY")  # récupère la clé


logger = logging.getLogger(__name__)

class OpenAIEngine:
    def __init__(self):
        self.sql_agent = SQLAgent()
        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.cost_per_1k_tokens = 0.002
        self.conversation_history = []
        self.max_history_tokens = 500
        self.response_templates = {
            "no_results": "Aucun résultat trouvé.",
            "db_error": "Erreur d'accès aux données. Veuillez reformuler.",
            "sql_error": "Requête SQL invalide ou non générée."
        }

    def count_tokens(self, text):
        return len(self.enc.encode(text))
    
    def get_student_info_by_name(self, full_name):
        """Récupère les infos d'un élève depuis la base de données"""
        return self.sql_agent.get_student_info_by_name(full_name)

    def _trim_history(self):
        while self.conversation_history and sum(msg['tokens'] for msg in self.conversation_history) > self.max_history_tokens:
            self.conversation_history.pop(0)

    def _build_response(self, response, sql_query=None, db_results=None, tokens=0, cost=0):
        return {
            "response": response,
            "sql_query": sql_query,
            "db_results": db_results,
            "tokens_used": tokens,
            "estimated_cost_usd": cost,
            "conversation_id": id(self.conversation_history)
        }

    def get_response(self, user_query):
                # ✨ Détection demande d'attestation
        if "attestation de présence" in user_query.lower():
            from pdf_utils.attestation import export_attestation_pdf

            # 👉 Tu peux rendre ça dynamique plus tard
            donnees_etudiant = {
                "nom": "Rania Zahraoui",
                "date_naissance": "15/03/2005",
                "matricule": "2023A0512",
                "etablissement": "Lycée Pilote de Sfax",
                "classe": "3ème Sciences",
                "annee_scolaire": "2024/2025",
                "lieu": "Sfax"
            }

            pdf_path = export_attestation_pdf(donnees_etudiant)
            return {
                "response": f"L'attestation a été générée : <a href='/{pdf_path.replace(os.sep, '/')}' download>Télécharger le PDF</a>"
            }

        try:
            query_tokens = self.count_tokens(user_query)
            self.conversation_history.append({
                'role': 'user',
                'content': user_query,
                'tokens': query_tokens
            })

            db_results = self.sql_agent.execute_natural_query(user_query)
            if not db_results:
                return self._build_response(self.response_templates["no_results"])

            prompt = {
                "role": "user",
                "content": (
                    f"Question: {user_query}\n"
                    f"Requête SQL générée: {self.sql_agent.last_generated_sql}\n"
                    f"Résultats:\n{json.dumps(db_results, ensure_ascii=False)[:800]}\n\n"
                    "Formule une réponse claire et concise en français avec les données ci-dessus."
                )
            }

            messages = [{
                "role": "system",
                "content": (
                    "Tu es un assistant pédagogique. Reformule les résultats SQL bruts en réponse naturelle, utile et claire."
                )
            }, prompt]

            response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=400)


            response_text = response.choices[0].message.content.strip()
            response_tokens = self.count_tokens(response_text)
            self.conversation_history.append({
                'role': 'assistant',
                'content': response_text,
                'tokens': response_tokens
            })
            self._trim_history()

            prompt_tokens = response.usage.prompt_tokens
            total_tokens = prompt_tokens + response_tokens
            cost = total_tokens / 1000 * self.cost_per_1k_tokens

            return self._build_response(
                response_text,
                self.sql_agent.last_generated_sql,
                db_results,
                total_tokens,
                cost
            )
        except Exception as e:
            logger.error(f"Erreur: {str(e)}", exc_info=True)
            return self._build_response(self.response_templates["db_error"])
