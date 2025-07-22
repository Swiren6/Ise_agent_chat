import re
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SemanticTemplateMatcher:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.templates = []
        self.template_vectors = None 

    def load_templates(self, templates: List[Dict]) -> None:
        if not templates:
            raise ValueError("La liste de templates ne peut pas être vide")
        
        # Filtrage des templates valides
        valid_templates = []
        template_texts = []
        
        for t in templates:
            if not isinstance(t, dict) or "template_question" not in t:
                continue
                
            normalized = self._normalize_template(t["template_question"])
            if normalized.strip():  # Ignore les textes vides après normalisation
                valid_templates.append(t)
                template_texts.append(normalized)
        
        if not valid_templates:
            raise ValueError(
                "Aucun template valide après filtrage. "
                "Vérifiez que les templates contiennent bien 'template_question' "
                "et que le texte n'est pas vide après normalisation."
            )
        
        self.templates = valid_templates
        self.template_vectors = self.vectorizer.fit_transform(template_texts)

    def _normalize_template(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        
        # Remplace les variables et normalise
        text = re.sub(r'\{.+?\}', 'VAR', text)
        text = text.lower().strip()
        
        # Garde uniquement le texte significatif
        return ' '.join([word for word in text.split() if len(word) > 1])
    
    def find_similar_template(self, question: str, threshold: float = 0.8) -> Tuple[Optional[Dict], float]:
        """
        Trouve le template le plus similaire à la question
        Args:
            question: La question à comparer
            threshold: Le seuil de similarité minimum
        Returns:
            Un tuple (template, score) ou (None, 0) si aucun template ne dépasse le seuil
        """
        if not self.templates:
            return None, 0.0
            
        # Transforme la question en vecteur TF-IDF
        question_vec = self.vectorizer.transform([self._normalize_template(question)])
        
        # Calcul des similarités
        similarities = cosine_similarity(question_vec, self.template_vectors)[0]
        
        # Trouver le meilleur match
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]
        
        if best_score >= threshold:
            return self.templates[best_idx], best_score
        return None, 0.0
