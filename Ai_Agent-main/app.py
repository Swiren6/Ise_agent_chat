from flask import Flask, request, jsonify
import logging
import re
import os
import json  # <- utile pour json.dumps plus bas
from datetime import datetime  # ✅ NÉCESSAIRE
from database import Database
from pdf_utils.attestation import export_attestation_pdf
from openai_engine import OpenAIEngine


app = Flask(__name__)
engine = OpenAIEngine()

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
db = Database()

@app.route('/check_notifications', methods=['GET'])
def check_exam_notifications():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # --- 1. Générer les notifications "examen" pour les examens à venir dans 7 jours max
        query = """
            SELECT * FROM repartitionexamen
            WHERE date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """
        cursor.execute(query)
        examens = cursor.fetchall()

        for examen in examens:
            date_exam = examen['date']
            days_before = (date_exam - datetime.today().date()).days

            idClasse = examen['idClasse']
            idMatiere = examen['idMatiere']
            date_exam_iso = date_exam.strftime("%Y-%m-%d")

            if days_before == 7:
                message = f"📆 L’examen approche ! Prévu dans 7 jours (le {date_exam.strftime('%d/%m/%Y')})."
            elif days_before == 2:
                message = f"📌 Rappel : Examen dans 2 jours (le {date_exam.strftime('%d/%m/%Y')}) pour la classe ID {idClasse} en matière ID {idMatiere}."
            elif days_before == 1:
                message = f"⚠️ Attention ! Examen demain (le {date_exam.strftime('%d/%m/%Y')}) pour la classe ID {idClasse} en matière ID {idMatiere}."
            else:
                continue

            check_query = """
                SELECT COUNT(*) AS count FROM notification_queue
                WHERE type = 'examen'
                AND CAST(JSON_EXTRACT(payload, '$.idClasse') AS UNSIGNED) = %s
                AND CAST(JSON_EXTRACT(payload, '$.idMatiere') AS UNSIGNED) = %s
                AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.date_exam')) = %s
            """
            cursor.execute(check_query, (idClasse, idMatiere, date_exam_iso))
            result = cursor.fetchone()

            if result["count"] == 0:
                insert_query = """
                    INSERT INTO notification_queue (type, payload, seen, created_at, message)
                    VALUES (%s, %s, %s, NOW(), %s)
                """
                payload = {
                    "idClasse": idClasse,
                    "idMatiere": idMatiere,
                    "date_exam": date_exam_iso
                }
                cursor.execute(insert_query, (
                    "examen",
                    json.dumps(payload),
                    0,
                    message
                ))

        conn.commit()

        # --- 2. Récupérer toutes les notifications non vues (seen = 0)
        cursor.execute("SELECT * FROM notification_queue WHERE seen = 0")
        notifications_non_vues = cursor.fetchall()

        messages = [{"message": notif["message"]} for notif in notifications_non_vues]

        # --- 3. Marquer ces notifications comme vues (seen = 1)
        if notifications_non_vues:
            ids = [str(notif['id']) for notif in notifications_non_vues]
            format_strings = ",".join(["%s"] * len(ids))
            update_query = f"UPDATE notification_queue SET seen = 1 WHERE id IN ({format_strings})"
            cursor.execute(update_query, ids)
            conn.commit()

        return jsonify(messages)

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


def validate_name(full_name):
    """Valide le format du nom"""
    return bool(re.match(r'^[A-Za-zÀ-ÿ\s\-\']{3,50}$', full_name))

@app.route('/')
def home():
    return app.send_static_file('chat.html')

@app.route('/chat', methods=['POST'])
def handle_chat():
    try:
        data = request.json
        user_query = data.get('query', '').strip()
        logger.info(f"Requête reçue: {user_query}")

        # Détection demande d'attestation
        if "attestation" in user_query.lower():
            name_match = re.search(
                r"(?:attestation\s+(?:de|pour)\s+)([A-Za-zÀ-ÿ\s\-\']+)", 
                user_query, 
                re.IGNORECASE
            )
            
            if not name_match:
                return jsonify({
                    "response": "Veuillez spécifier un nom (ex: 'attestation de Nom Prénom')"
                })

            full_name = name_match.group(1).strip()
            
            if not validate_name(full_name):
                return jsonify({
                    "response": "Format de nom invalide. Utilisez uniquement des lettres et espaces"
                })

            # Récupération des données
            student_data = engine.get_student_info_by_name(full_name)
            
            if not student_data:
                return jsonify({
                    "response": f"Aucun élève trouvé avec le nom '{full_name}'"
                })

            # Harmoniser les champs pour le PDF
            student_data['nom_complet'] = student_data['nom']
            student_data['lieu_naissance'] = student_data['lieu_de_naissance']
            student_data['annee_scolaire'] = "2024/2025"

            # Génération du PDF
            try:
                pdf_path = export_attestation_pdf(student_data)

                filename = os.path.basename(pdf_path)
                
                return jsonify({
                    "response": (
                        f"✅ Attestation générée pour {student_data['nom_complet']}\n\n"
                        f"<a href='/static/{filename}' download>Télécharger</a>"
                    ),
                    "pdf_url": f"/static/{filename}"
                })
            except Exception as e:
                logger.error(f"Erreur génération PDF: {str(e)}")
                return jsonify({
                    "response": "Erreur lors de la génération du document"
                })

        # Traitement des autres requêtes
        response = engine.get_response(user_query)
        return jsonify({"response": str(response)})

    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({"error": "Une erreur est survenue"}), 500

if __name__ == '__main__':
    app.run(debug=True)