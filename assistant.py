from db_config import get_db_connection
from llm_utils import ask_llm
from langchain_community.utilities import SQLDatabase
from typing import List, Dict, Optional, Any, Tuple
from llm_utils import ask_llm 
from langchain.prompts import PromptTemplate
import os
import json
from template_matcher.matcher import SemanticTemplateMatcher
import re
from pathlib import Path
from cache_manager import CacheManager

PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["input", "table_info", "relevant_domain_descriptions", "relations"],
    template=f"""
[SYSTEM] Vous êtes un assistant SQL expert pour une base de données scolaire.
Votre rôle est de traduire des questions en français en requêtes SQL MySQL.

ATTENTION: 
**l'année scolaire se trouve dans anneescolaire.AnneeScolaire non pas dans Annee 
** si on dit l'annee XXXX/YYYY on parle de l'année scolaire XXXX/YYYY 
**les table eleve et parent ne contienne pas les noms et les prenoms . ils se trouvent dans la table personne.
**les table eleve et parent ne contienne pas les numéro de telephnone Tel1 et Tel2 . ils se trouvent dans la table personne.
**les colonnes principale  du table personne sont : id, NomFr, PrenomFr, NomAr , PrenomAr, Cin,AdresseFr, AdresseAr, Tel1, Tel2,Nationalite,Localite,Civilite.
**la trimestre 3 est d id 33, trimestre 2 est d id 32 , trimestre 1 est d id 31.
**lorsque on veut avoir l id d un eleve  on fait cette jointure : 
id_inscription IN (
        SELECT id
        FROM inscriptioneleve
        WHERE Eleve IN (
            SELECT id
            FROM eleve
            WHERE IdPersonne = "numéro de id "
        )
**lorsque on veut savoir l id de la séance on fait la jointure suivante : s.id=e.SeanceDebut  avec s pour la seance et e pour Emploidutemps 
**lorsque on demande l etat de paiement on ne mais pas p.Annuler=0 avec p paiement ni CASE
        WHEN p.Annuler = 1 THEN 'Annulé'
        ELSE 'Actif'
    END AS statut_paiement.
**lorsque on veut savoir le paiement extra d un eleve on extrait le motif_paiement, le totalTTC  et le reste en faisant  la jointure entre le paiementextra et paiementextradetails d'une coté et paiementextra et paiementmotif d'une autre coté .
**lorsque on demande les détails de paiement scolaire on extrait le mode de reglement ,numéro de chèque , montant et la date de l'opération. 
**lorsque on demande l'mploi du temps d'un classe précie avec un jour précie on extrait le nom , le prénom de l'enseignant ,le nom de la matière , le nom de la salle , le debut et la fin de séance et le libelle de groupe (par classe...)
**Les coordonées de debut et de la fin de séance se trouve dans le table emploidutemps sous forme d'id ,les covertir en heures a l'aide de table seance . 
**la semaine A est d'id 2 , la semaine B est d'id 3 , Sans semaine d'id 1.
**les colonnes principale  du table personne sont : id, NomFr, PrenomFr, NomAr , PrenomAr, Cin,AdresseFr, AdresseAr, Tel1, Tel2,Nationalite,Localite,Civilite.
**pour les nom de jour en français on a une colone libelleJourFr avec mercredi c est ecrite Mercredi . 
**utiliser des JOINs explicites . exemple au lieu de :WHERE
    e.Classe = (SELECT id FROM classe WHERE CODECLASSEFR = '7B2')
    AND e.Jour = (SELECT id FROM jour WHERE libelleJourFr = 'Mercredi')
    ecrire:
 JOIN
     jour j ON e.Jour = j.id AND j.libelleJourFr = 'Mercredi'
JOIN
     classe c ON e.Classe = c.id AND c.CODECLASSEFR = '7B2'
**les résultats des trimestres se trouve dans le table Eduresultatcopie .
**l id de l eleve est liée par l id de la personne par Idpersonne 
**lorsqu'on demande les moyennes par matières pour une trimestre précise voici la requette qu on applique :
SELECT em.libematifr AS matiere ,ed.moyemati AS moyenne, ex.codeperiexam AS codeTrimestre FROM
           Eduperiexam ex, Edumoymaticopie ed, Edumatiere em, Eleve e
           WHERE e.idedusrv=ed.idenelev and ed.codemati=em.codemati and
           ex.codeperiexam=ed.codeperiexam  and  e.Idpersonne=(id_de la personne) and ed.moyemati not like '0.00' and ed.codeperiexam = ( id de la trimestre  ;
**les eleves nouvellemmnent inscris ont un TypeInscri="N" et les eleves qui ont etudié auparavant a l'ecole ont TypeInscri="R".
**un éleves n'est pas réinscri est éleves qui est inscrits pendant l'année précédante et pas pour cette année . 
**la décision d'acceptation consernent seulement les nouveaux eleves inscrits a l'ecole.
**pour les cheques a echeance non valides consulter la table reglementeleve_echeancier .
**les cheques echancier non valide le champ isvalide=0.

Voici la structure détaillée des tables pertinentes pour votre tâche (nom des tables, colonnes et leurs types) :
{{table_info}}

---
**Description des domaines pertinents pour cette question :**
{{relevant_domain_descriptions}}

---
**Informations Clés et Relations Fréquemment Utilisées pour une meilleure performance :**
{{relations}}

---
**Instructions pour la génération SQL :**
1.  Répondez UNIQUEMENT par une requête SQL MySQL valide et correcte.
2.  Ne mettez AUCUN texte explicatif ou commentaire avant ou après la requête SQL. La réponse doit être purement la requête.
3.  **Sécurité :** Générez des requêtes `SELECT` uniquement. Ne générez **JAMAIS** de requêtes `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` ou toute autre commande de modification/suppression de données.
4.  **Gestion de l'Année Scolaire :** Si l'utilisateur mentionne une année au format 'YYYY-YYYY' (ex: '2023-2024'), interprétez-la comme équivalente à 'YYYY/YYYY' et utilisez ce format pour la comparaison sur la colonne `Annee` de `anneescolaire` ou pour trouver l'ID correspondant.
5.  **Robustesse aux Erreurs et Synonymes :** Le modèle doit être tolérant aux petites fautes de frappe et aux variations de langage. Il doit s'efforcer de comprendre l'intention de l'utilisateur même si les termes ne correspondent pas exactement aux noms de colonnes ou de tables. Par exemple, "eleves" ou "étudiants" devraient être mappés à la table `eleve`. "Moyenne" ou "résultat" devraient faire référence à `dossierscolaire.moyenne_general` ou `edumoymati`.


Question : {{input}}
Requête SQL :
"""
)

class SQLAssistant:
    def __init__(self):
        self.db = get_db_connection()
        self.relations_description = self.load_relations()
        self.domain_descriptions = self.load_domain_descriptions()
        self.domain_to_tables_mapping = self.load_domain_to_tables_mapping()
        self.ask_llm = ask_llm
        self.cache =CacheManager()
        # Initialisation du matcher
        self.template_matcher = SemanticTemplateMatcher()
        
        try:
            self.templates_questions = self.load_question_templates()
            if self.templates_questions:
                print(f"✅ {len(self.templates_questions)} templates chargés")
                self.template_matcher.load_templates(self.templates_questions)
            else:
                print("⚠️ Aucun template valide - fonctionnement en mode LLM seul")
                
        except ValueError as e:
            print(f"❌ Erreur de chargement des templates: {str(e)}")
            self.templates_questions = []

    def load_question_templates(self) -> list:
        try:
            with open('templates_questions.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('questions', [])
        except FileNotFoundError:
            print("⚠️ Fichier templates_questions.json non trouvé. Création d'un fichier vide.")
            Path('templates_questions.json').touch()
            return []
        except Exception as e:
            print(f"❌ Erreur lors du chargement des templates: {e}")
            return []
 
    def find_matching_template(self, question: str) -> Optional[Dict[str, Any]]:
        exact_match = self._find_exact_template_match(question)
        if exact_match:
            return exact_match
        
        semantic_match, score = self.template_matcher.find_similar_template(question)
        if semantic_match:
            print(f"🔍 Template sémantiquement similaire trouvé (score: {score:.2f})")
            return self._extract_variables(question, semantic_match)
        
        return None

    def _find_exact_template_match(self, question: str) -> Optional[Dict[str, Any]]:
        cleaned_question = question.rstrip(' ?')
        for template in self.templates_questions:
            pattern = template["template_question"]
            regex_pattern = re.sub(r'\{(.+?)\}', r'(?P<\1>.+?)', pattern)
            match = re.fullmatch(regex_pattern, cleaned_question, re.IGNORECASE)
            if match:
                variables = {k: v.strip() for k, v in match.groupdict().items()}
                return {
                    "template": template,
                    "variables": variables if variables else {}
                }
        return None
    
    def _extract_variables(self, question: str, template: Dict) -> Dict[str, Any]:
        template_text = template["template_question"]
        variables = {}

        annee_pattern = r"(20\d{2}[-\/]20\d{2})"
        annee_match = re.search(annee_pattern, question)
        if annee_match:
            variables["AnneeScolaire"] = annee_match.group(1).replace("-", "/")
        
        var_names = re.findall(r'\{(.+?)\}', template_text)
        for var_name in var_names:
            if var_name not in variables:  
                keyword_pattern = re.escape(template_text.split(f"{{{var_name}}}")[0].split()[-1])
                pattern = fr"{keyword_pattern}\s+([^\s]+)"
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    variables[var_name] = match.group(1).strip(",.?!")
        
        return {
            "template": template,
            "variables": variables if variables else {}
        }

    def generate_query_from_template(self, template: Dict, variables: Dict) -> str:
        requete = template["requete_template"]
        if not variables:
            return requete
        
        for var_name, var_value in variables.items():
            clean_value = str(var_value).split('?')[0].strip(",.!?\"'")
            
            if var_name.lower() == "anneescolaire":
                clean_value = clean_value.replace("-", "/")
            
            requete = requete.replace(f'{{{var_name}}}', clean_value)
        
        return requete
    
    def load_domain_descriptions(self) -> tuple[Dict[str, str], Dict[str, List[str]]]:
        with open('prompts/domain_descriptions.json') as f:
            return json.load(f)
        
    def load_relations(self) -> str:
        with open("prompts/relations.txt", "r") as f:
            return f.read()
        
    def load_domain_to_tables_mapping(self) ->str:
        with open("prompts/domain_tables_mapping.json", "r") as f:
            return json.load(f)

    def get_relevant_domains(self, query: str, domain_descriptions: Dict[str, str]) -> List[str]:
        """Identifies relevant domains based on a user query using DeepSeek."""
        domain_desc_str = "\n".join([f"- {name}: {desc}" for name, desc in domain_descriptions.items()])
        domain_prompt_content = f"""
        Based on the following user question, identify ALL relevant domains from the list below.
        Return only the names of the relevant domains, separated by commas. If no domain is relevant, return 'None'.

        User Question: {query}

        Available Domains and Descriptions:
        {domain_desc_str}

        Relevant Domains (comma-separated):
        """
        
        try:
            response = self.ask_llm(domain_prompt_content)
            domain_names = response.strip()
            
            if domain_names.lower() == 'none' or not domain_names:
                return []
            return [d.strip() for d in domain_names.split(',')]
        except Exception as e:
            print(f"❌ Erreur lors de l'identification des domaines: {e}")
            return []
    
    def get_tables_from_domains(self, domains: List[str], domain_to_tables_map: Dict[str, List[str]]) -> List[str]:
        """Retrieves all tables associated with the given domains."""
        tables = []
        for domain in domains:
            tables.extend(domain_to_tables_map.get(domain, []))
        return sorted(list(set(tables)))
    
    def ask_question(self, question: str) -> tuple[str, str]:
        # 1. Vérifier le cache avec la nouvelle approche
        cached = self.cache.get_cached_query(question)
        if cached:
            sql_template, variables = cached
            # Remplacer les placeholders dans la requête SQL
            sql_query = sql_template
            for column, value in variables.items():
                sql_query = sql_query.replace(f"{{{column}}}", value)
            
            print("⚡ Requête récupérée depuis le cache (similarité sémantique)")
            try:
                result = self.db.run(sql_query)
                return sql_query, self.format_result(result, question)
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
        # 2. Vérifier les templates prédéfinis
        template_match = self.find_matching_template(question)
        if template_match:
            print("🔍 Question correspond à un template pré-enregistré")
            sql_query = self.generate_query_from_template(
                template_match["template"],
                template_match["variables"]
            )
            print(f"⚡ Requête générée à partir du template: {sql_query}")
            try:
                result = self.db.run(sql_query)
                formatted_result = self.format_result(result, question)
                # Mise en cache avec la nouvelle méthode
                self.cache.cache_query(question, sql_query)
                return sql_query, formatted_result
            except Exception as db_error:
                return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
        # 3. Génération via LLM
        print("🔍 Aucun template trouvé, utilisation du LLM")
        prompt = PROMPT_TEMPLATE.format(
            input=question,
            table_info=self.db.get_table_info(),
            relevant_domain_descriptions="\n".join(self.domain_descriptions.values()),
            relations=self.relations_description
        )

        sql_query = self.ask_llm(prompt)
        if not sql_query:
            return "", "❌ La requête générée est vide."

        sql_query = sql_query.strip()
        print(f"🔍 Requête générée: {sql_query}")

        try:
            result = self.db.run(sql_query)
            formatted_result = self.format_result(result, question)
            self.cache.cache_query(question, sql_query)
            return sql_query, formatted_result
        except Exception as db_error:
            return sql_query, f"❌ Erreur d'exécution SQL : {str(db_error)}"
        
    def format_result(self, result: str, question: str = "") -> str:
        """
        Formate les résultats SQL bruts en une table lisible
        Args:
            result: Le résultat brut de la requête SQL
            question: La question originale (optionnelle)
        Returns:
            str: Le résultat formaté ou un message approprié
        """
        if not result or result.strip() in ["[]", ""] or "0 rows" in result.lower():
            return "✅ Requête exécutée mais aucun résultat trouvé."
        
        try:
            lines = [line.strip() for line in result.split('\n') if line.strip()]
            if len(lines) == 1 and lines[0].startswith('(') and lines[0].endswith(')'):
                value = lines[0][1:-1].strip()  
                return f"Résultat : {value}"
            
            if len(lines) > 1:
                headers = [h.strip() for h in lines[0].split('|')]
                rows = []
                
                for line in lines[1:]:
                    row = [cell.strip() for cell in line.split('|')]
                    rows.append(row)
                
                formatted = []
                if question:
                    formatted.append(f"Résultats pour: {question}\n")
                
                # En-tête
                header_line = " | ".join(headers)
                formatted.append(header_line)
                
                # Séparateur
                separator = "-+-".join(['-' * len(h) for h in headers])
                formatted.append(separator)
                
                # Données
                for row in rows:
                    formatted.append(" | ".join(row))
                
                return "\n".join(formatted)
            
            return f"Résultat brut:\n{result}"
        
        except Exception as e:
            return f"❌ Erreur de formatage: {str(e)}\nRésultat brut:\n{result}"