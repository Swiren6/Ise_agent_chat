from fpdf import FPDF
from database import Database
from datetime import date
import os

def export_bulletin_pdf(idenelev: int) -> str:
    db = Database()
    query = """
    SELECT e.*, m.NomMatiereFr
    FROM edumoymaticopie e
    LEFT JOIN matiere m ON e.codemati = m.id
    WHERE e.idenelev = %s
    """
    result = db.execute_query(query, (idenelev,))

    if not result['success'] or not result['data']:
        raise ValueError("Aucune donnée trouvée pour cet élève.")

    rows = result['data']

    # Calcul moyenne générale (sur les moyemati numériques valides)
    notes = []
    for r in rows:
        try:
            notes.append(float(r['moyemati']))
        except (ValueError, TypeError):
            continue

    moyenne_generale = sum(notes) / len(notes) if notes else 0

    # Déterminer la mention
    if moyenne_generale >= 16:
        mention = "Très bien"
    elif moyenne_generale >= 14:
        mention = "Bien"
    elif moyenne_generale >= 12:
        mention = "Assez bien"
    elif moyenne_generale >= 10:
        mention = "Passable"
    else:
        mention = "Insuffisant"

    # Création PDF formel
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Lycée Pilote de Sfax", ln=True, align='C')
    pdf.set_font("Arial", '', 14)
    pdf.cell(0, 10, "Bulletin Scolaire Officiel", ln=True, align='C')
    pdf.ln(10)

    # Infos élève
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, f"Identifiant élève : {idenelev}", ln=True)
    pdf.cell(0, 8, f"Année scolaire : 2024 / 2025", ln=True)
    pdf.cell(0, 8, f"Date de génération : {date.today().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(10)

    # Tableau des matières
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 8, "Matière", 1)
    pdf.cell(40, 8, "Moyenne", 1)
    pdf.cell(30, 8, "Rang", 1)
    pdf.cell(40, 8, "Période", 1)
    pdf.ln()

    pdf.set_font("Arial", '', 12)
    for r in rows:
        nom_matiere = r['NomMatiereFr'] if r['NomMatiereFr'] else str(r['codemati'])
        pdf.cell(50, 8, nom_matiere, 1)
        pdf.cell(40, 8, str(r['moyemati']), 1)
        pdf.cell(30, 8, str(r['rangmati']), 1)
        pdf.cell(40, 8, str(r['codeperiexam']), 1)
        pdf.ln()


    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Moyenne générale : {moyenne_generale:.2f} / 20", ln=True)
    pdf.cell(0, 10, f"Mention : {mention}", ln=True)

    # Signature
    pdf.ln(20)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, "Signature du directeur", ln=True, align='R')
    pdf.cell(0, 10, "____________________", ln=True, align='R')

    # Sauvegarde
    os.makedirs("static", exist_ok=True)
    output_path = f"static/bulletin_{idenelev}.pdf"
    pdf.output(output_path)
    return output_path
