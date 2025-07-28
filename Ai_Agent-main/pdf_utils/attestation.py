from fpdf import FPDF
from datetime import datetime
import os
import arabic_reshaper
from bidi.algorithm import get_display


def export_attestation_pdf(donnees):
    pdf = FPDF()
    pdf.add_page()

    # Ajout de la police Amiri
    font_path_regular = r"C:/Users/rania/Downloads/Ai_Agent-main/Ai_Agent-main/pdf_utils/fonts/Amiri-1.002/Amiri-Regular.ttf"
    font_path_bold = r"C:/Users/rania/Downloads/Ai_Agent-main/Ai_Agent-main/pdf_utils/fonts/Amiri-1.002/Amiri-Bold.ttf"
    pdf.add_font("Amiri", "", font_path_regular, uni=True)
    pdf.add_font("Amiri", "B", font_path_bold, uni=True)

    pdf.set_font("Amiri", size=14)

    # Fonction pour inverser le texte arabe (reshaping + bidi)
    def render_ar(text):
        return get_display(arabic_reshaper.reshape(text))

    # Logo à gauche
    logo_path = "C:/Users/rania/Downloads/logo_ise.jpeg"
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=10, w=30)

    # En-tête arabe à droite
    pdf.set_xy(110, 10)
    pdf.multi_cell(
        0, 8,
        render_ar("الجمهورية التونسية\nوزارة التربية\nالمندوبية الجهوية للتربية بنابل\nالمدرسة الدولية للنخبة"),
        align='R'
    )

    pdf.ln(30)

    # Titre centré
    pdf.set_font("Amiri", 'B', 16)
    pdf.cell(0, 10, "ATTESTATION DE PRÉSENCE", ln=True, align='C')
    pdf.ln(10)

    # Texte d’introduction
    pdf.set_font("Amiri", '', 14)
    texte_intro = (
        "Je soussignée, Mme Balkis Zrelli, Directrice du Collège et Lycée International School Of Elite, atteste que:\n"
    )
    pdf.multi_cell(0, 10, texte_intro)

    # Nom centré, gras, taille 16
    nom = donnees.get('nom_complet') or donnees.get('nom') or 'Nom non précisé'
    pdf.set_font("Amiri", 'B', 16)
    pdf.cell(0, 10, nom.upper(), ln=True, align='C')

    


    # Date de naissance centré, gras, taille 14
    pdf.set_font("Amiri", 'B', 14)
    '''date_naissance_text = f"Né(e) le: {donnees.get('date_naissance', '')} à {donnees.get('lieu_naissance', 'Lieu non précisé')}"'''
    #pdf.cell(0, 10, date_naissance_text, ln=True, align='C')

    # Suite du texte normal
    classe = donnees.get('classe', 'Classe non précisée')
    pdf.set_font("Amiri", '', 14)
    # Texte avant la classe
    texte_avant_classe = "Est inscrit(e) et poursuit régulièrement ses études en "
    texte_apres_classe = " de l'année scolaire 2024/2025\nEn foi de quoi, la présente attestation lui est établie pour servir et valoir ce que de droit.\n"

    # Partie normale
    pdf.set_font("Amiri", '', 14)
    pdf.write(8, texte_avant_classe)

    # Classe en gras
    pdf.set_font("Amiri", 'B', 14)
    pdf.write(8, classe)

    # Revenir à la police normale
    pdf.set_font("Amiri", '', 14)
    pdf.write(8, texte_apres_classe)

    # Signature
    pdf.ln(20)
    pdf.cell(0, 10, "Signature & Cachet :", ln=True, align='R')
    pdf.cell(0, 10, "_______________________", ln=True, align='R')

    # Sauvegarde du PDF
    os.makedirs("static", exist_ok=True)
    matricule = donnees.get('matricule', '0000')
    chemin = f"static/attestation_presence_{matricule}.pdf"
    pdf.output(chemin)
    return chemin
