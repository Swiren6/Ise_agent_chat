import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import hashlib
import re
from collections import defaultdict

class CacheManager:
    def __init__(self, cache_file: str = "sql_query_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()
        
        # Patterns de base pour les valeurs structurées
        self.auto_patterns = {
            r'\b([A-Z]{3,})\s+([A-Z]{3,})\b': 'NomPrenom',
            r'\b\d+[A-Z]\d+\b': 'CODECLASSEFR', 
            r'\b(20\d{2}[/-]20\d{2})\b': 'AnneeScolaire',  
        }
        self.trimestre_mapping = {
            '1er trimestre': 31,
            '1ère trimestre': 31,
            'premier trimestre': 31,
            '2ème trimestre': 32,
            'deuxième trimestre': 32,
            '3ème trimestre': 33,
            '3éme trimestre': 33,
            'troisième trimestre': 33,
            'trimestre 1': 31,
            'trimestre 2': 32,
            'trimestre 3': 33
        }
        self.discovered_patterns = defaultdict(list)

    def _load_cache(self) -> Dict[str, Any]:
        if not self.cache_file.exists():
            return {}
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    def _extract_parameters(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Détection intelligente des paramètres"""
        variables = {}
        normalized = text
        
        for term, code in self.trimestre_mapping.items():
            if term in normalized.lower():
                normalized = normalized.replace(term, "{codeperiexam}")
                variables["codeperiexam"] = str(code)
                break
        # 1. Détection des motifs connus
        for pattern, param_type in self.auto_patterns.items():
            matches = list(re.finditer(pattern, normalized))
            for match in reversed(matches):  # Traiter de droite à gauche pour éviter les problèmes d'index
                full_match = match.group(0)
                
                if param_type == 'NomPrenom':
                    nom, prenom = match.groups()
                    normalized = normalized.replace(full_match, "{NomFr} {PrenomFr}")
                    variables.update({"NomFr": nom, "PrenomFr": prenom})
                else:
                    value = match.group(1) if len(match.groups()) > 0 else full_match
                    normalized = normalized.replace(full_match, f"{{{param_type}}}")
                    variables[param_type] = value

        # 2. Détection des valeurs entre quotes non encore traitées
        quoted_values = re.findall(r"['\"]([^'\"]+)['\"]", normalized)
        for val in quoted_values:
            if val not in variables.values():  # Pas déjà traité
                if val.isupper() and len(val.split()) == 1:
                    param_name = "NomFr" if "nom" in normalized.lower() else "Valeur"
                    normalized = normalized.replace(f"'{val}'", f"'{{{param_name}}}'")
                    variables[param_name] = val

        return normalized, variables
    
    def _replace_matches(self, text: str, pattern: str, param_name: str) -> Tuple[str, str]:
        """Remplace les occurences et retourne la valeur trouvée"""
        matches = re.finditer(pattern, text)
        value = None
        for match in matches:
            value = match.group(1) if len(match.groups()) > 0 else match.group(0)
            text = text.replace(value, f"{{{param_name}}}")
        return text, value
    
    def _infer_parameter_name(self, value: str, context: str) -> str:
        """Infère le nom du paramètre basé sur le contexte"""
        if value.isdigit():
            return "ID"
        
        # Analyse le contexte pour deviner le type de paramètre
        if "nom" in context.lower():
            return "NomFr" if value.isupper() else "Nom"
        elif "prenom" in context.lower():
            return "PrenomFr"
        elif "matiere" in context.lower():
            return "Matiere"
        elif "salle" in context.lower():
            return "Salle"
        
        # Enregistre le nouveau motif pour usage futur
        pattern = re.escape(value)
        self.discovered_patterns[pattern].append(context)
        return "VALUE"
    
    def _generate_cache_key(self, question: str) -> str:
        """Génère une clé basée sur la question normalisée"""
        normalized_question, _ = self._extract_parameters(question)  # Utilise la nouvelle méthode
        return hashlib.md5(normalized_question.encode('utf-8')).hexdigest()

    def _normalize_question(self, question: str) -> Tuple[str, Dict[str, str]]:
        """Alternative à extract_parameters pour une compatibilité ascendante"""
        return self._extract_parameters(question)  # Délègue à la nouvelle méthode

    def _normalize_sql(self, sql: str, variables: Dict[str, str]) -> str:
        """Normalisation SQL avancée"""
        # Protection des mots-clés SQL
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'AND', 'OR']
        protected = []
        
        if "codeperiexam" in variables:
            code = variables["codeperiexam"]
            sql = re.sub(r'codeperiexam\s*=\s*\d+', f'codeperiexam = {code}', sql)
            sql = re.sub(r"'?\d+'?\s*=\s*codeperiexam", f"'{code}' = codeperiexam", sql)
        def protect(match):
            protected.append(match.group(0))
            return f"__PROTECTED_{len(protected)-1}__"
        
        temp_sql = re.sub('|'.join(keywords), protect, sql, flags=re.IGNORECASE)
        
        # Remplacement des variables
        for param, value in variables.items():
            for fmt in [f"'{value}'", f'"{value}"', value]:
                if fmt in temp_sql:
                    temp_sql = temp_sql.replace(fmt, f"{{{param}}}")
        
        # Restauration des mots-clés
        for i, kw in enumerate(protected):
            temp_sql = temp_sql.replace(f'__PROTECTED_{i}__', kw)
            
        return temp_sql

    def get_cached_query(self, question: str) -> Optional[Tuple[str, Dict[str, str]]]:
        """Version compatible avec la détection automatique"""
        normalized_question, variables = self._extract_parameters(question)
        key = self._generate_cache_key(normalized_question)
        
        if key not in self.cache:
            return None
            
        cached = self.cache[key]
        
        # Reconstruit les variables actuelles
        current_vars = {}
        for param in re.findall(r'\{(\w+)\}', cached['sql_template']):
            if param in variables:
                current_vars[param] = variables[param]
        
        return cached['sql_template'], current_vars

    def cache_query(self, question: str, sql_query: str):
        """Version finale de mise en cache"""
        norm_question, vars_question = self._extract_parameters(question)
        norm_sql = self._normalize_sql(sql_query, vars_question)
        
        key = hashlib.md5(norm_question.encode()).hexdigest()
        self.cache[key] = {
            'question_template': norm_question,
            'sql_template': norm_sql
        }
        self._save_cache()