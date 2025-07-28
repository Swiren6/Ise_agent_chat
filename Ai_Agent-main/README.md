📚 Agent IA d’Analyse de Base de Données Scolaire

🚀 Présentation
Ce projet implémente un assistant intelligent capable de comprendre des questions en langage naturel et de répondre en interrogeant automatiquement une base de données scolaire MySQL. L’agent génère des requêtes SQL sécurisées via OpenAI, exécute les requêtes, puis reformule les réponses en langage clair.

⚙️ Fonctionnalités
Compréhension naturelle des questions utilisateurs.
Génération automatique de requêtes SQL sécurisées
Exécution dynamique sur une base MySQL locale.
Réponses claires et contextualisées en français.
Gestion intelligente de plus de 200 tables, catégorisées en 3 prompts pour optimiser la précision.
Historique de conversation avec gestion du budget token.

🛠️ Stack technique
Python 3.10+
Flask : API REST
OpenAI GPT-3.5 Turbo via SDK officiel
MySQL Connector/Python
tiktoken pour gestion des tokens
dotenv pour variables d’environnement

📂 Structure du projet

.
├── app.py                # API Flask principale
├── openai_engine.py      # Gestionnaire OpenAI & logique de conversation
├── sql_agent.py          # Génération + exécution SQL
├── database.py           # Connexion MySQL
├── prompt1.txt           # Prompt catégorie 1
├── prompt2.txt           # Prompt catégorie 2
├── prompt3.txt           # Prompt catégorie 3
├── requirements.txt      # Dépendances Python
├── .env                  # Variables sensibles (clé API, DB...)
└── README.md             # Ce fichier

🔧 Installation

1.Cloner le dépôt :
git clone git https://github.com/Swiren6/Ai_Agent.git

2.Créer un environnement virtuel et installer les dépendances :
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

3.Configurer le fichier .env avec :
OPENAI_API_KEY=clef_openai
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=ton_mot_de_passe
DB_NAME=nom_de_la_base

4.Lancer l’application :


python app.py

🗣️ Utilisation
Accéder à http://localhost:5000 pour interagir via l’interface (chat.html).

Envoyer des questions en français.
L’agent répond en générant et exécutant la requête SQL adaptée.

⚠️ Conseils & limites
Les prompts sont optimisés pour limiter les tables utilisées et éviter les requêtes trop lourdes.
Les requêtes dangereuses (DROP, DELETE, etc.) sont bloquées automatiquement.
Le système ne gère pas encore les questions hors domaine scolaire.


