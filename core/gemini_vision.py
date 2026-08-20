# core/gemini_vision.py
"""
Vision Gemini - Utilisé en fallback quand l'OCR/Gemini texte ne trouve pas tout.
Analyse les images des pages PDF pour détecter les tampons, annotations manuscrites,
et documents douaniers.
"""

import os
import json
import re
import tempfile
from typing import Dict, Any, Optional, List
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# ⭐ Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    GEMINI_API_KEY = "AQ.Ab8RN6JSUNibDLAnZxiDj6kbKTvdARXuPl2j8KW2MPIJBP34DA"

GEMINI_VISION_MODEL = "gemini-2.0-flash-lite"  # Plus stable pour la vision

print("="*60)
print("🔴 CONFIGURATION GEMINI VISION")
print(f"📌 API Key: {GEMINI_API_KEY[:10]}...")
print(f"📌 Modèle Vision: {GEMINI_VISION_MODEL}")
print("="*60)

try:
    import google as genai
    genai.configure(api_key=GEMINI_API_KEY)
    VISION_DISABLED = False
    print("✅ Gemini Vision configuré avec succès")
except ImportError:
    print("⚠️ google-generativeai non installé")
    VISION_DISABLED = True
except Exception as e:
    print(f"⚠️ Erreur configuration Vision: {e}")
    VISION_DISABLED = True


def charger_toutes_les_pages(chemin_fichier: str, dpi: int = 150, max_pages: int = 15) -> List[Image.Image]:
    """
    Convertit TOUTES les pages d'un PDF en images.
    Limité à max_pages pour contrôler les coûts.
    """
    if chemin_fichier.lower().endswith('.pdf'):
        pages = convert_from_path(chemin_fichier, dpi=dpi)
        if len(pages) > max_pages:
            print(f"   ⚠️ Document trop long ({len(pages)} pages), limité à {max_pages} pages")
            pages = pages[:max_pages]
        return pages
    return [Image.open(chemin_fichier)]


PROMPT_VISION = """
Tu es un expert en extraction de données de documents financiers et commerciaux marocains.

⚠️ RÈGLE D'OR :
- Regarde TOUTES les pages/images fournies.
- Extrais UNIQUEMENT ce que tu vois CLAIREMENT.
- Si tu as un DOUTE, mets false ou null.
- N'INVENTE RIEN.

📋 TÂCHE : Extrais l'objet de commande et détecte les documents annexes.

🎯 PARTIE 1 : OBJET DE COMMANDE
L'objet de commande décrit la prestation, le service ou le produit facturé.

🔍 OÙ CHERCHER (par ordre de priorité) :
1. Les titres "OBJET", "Objet", "PRESTATION", "Prestation"
2. Les tampons ou annotations
3. Les colonnes "DESIGNATION", "Désignation", "ACTIVITÉ", "Activité" dans les tableaux
4. Les en-têtes de facture
5. La description des marchandises

⚠️ RÈGLES :
- Recopie le texte EXACTEMENT comme il apparaît
- Si c'est une facture de transport → "Transport et logistique"
- Si c'est une facture de fourniture → le nom du produit
- Si tu vois "DEBOURS" → Prestation de transport/logistique

🎯 PARTIE 2 : DOCUMENTS ANNEXES

Scanne TOUTES les pages. Cherche :

1. attestation_rib : "RIB", "IBAN", ou numéro de compte bancaire
2. bon_livraison : "BL number:", "BON DE LIVRAISON", "DELIVERY FORM"
3. pv_reception : "PV", "PROCES VERBAL DE RECEPTION"
4. pv_location : "PV DE LOCATION", "CONTRAT DE LOCATION"
5. feuille_presence : "FEUILLE DE PRESENCE"
6. certificats_rapport : "CERTIFICAT", "RAPPORT", "ATTESTATION"
7. engagement_importation : "ENGAGEMENT D'IMPORTATION", "DUM", "DECLARATION A ENREGISTREMENT"
8. quittance_douane : "FICHE DE LIQUIDATION", "QUITTANCE DOUANE", "LIQUIDATION DES DROITS"

📄 RÉPONSE UNIQUEMENT EN JSON :
{
  "objet_commande": "texte ou null",
  "confiance": "haute/moyenne/faible",
  "source": "où tu as trouvé",
  "annexes": {
    "attestation_rib": true/false,
    "bon_livraison": true/false,
    "pv_reception": true/false,
    "pv_location": true/false,
    "feuille_presence": true/false,
    "certificats_rapport": true/false,
    "engagement_importation": true/false,
    "quittance_douane": true/false
  }
}
"""


def analyser_avec_vision(file_path: str) -> Dict[str, Any]:
    """
    Analyse le document avec Gemini Vision (images).
    Retourne le résultat JSON ou un dict d'erreur.
    """
    if VISION_DISABLED:
        return {"erreur": "Vision désactivée"}
    
    try:
        print(f"   👁️ Vision Gemini - Analyse de toutes les pages...")
        
        # Convertir en images
        pages = charger_toutes_les_pages(file_path)
        if not pages:
            return {"erreur": "Aucune page trouvée"}
        
        print(f"   📄 {len(pages)} pages à analyser en vision")
        
        # Créer le modèle
        model = genai.GenerativeModel(GEMINI_VISION_MODEL)
        
        # Envoyer le prompt + toutes les images
        contenu = [PROMPT_VISION] + pages
        
        response = model.generate_content(contenu)
        texte_reponse = response.text.strip()
        
        # Nettoyer la réponse
        texte_reponse = re.sub(r'^```json\s*|\s*```$', '', texte_reponse, flags=re.MULTILINE).strip()
        
        # Extraire le JSON
        if '{' in texte_reponse:
            start = texte_reponse.find('{')
            end = texte_reponse.rfind('}') + 1
            texte_reponse = texte_reponse[start:end]
        
        resultat = json.loads(texte_reponse)
        resultat['_nb_pages_analysees'] = len(pages)
        
        print(f"   ✅ Vision - Objet: {resultat.get('objet_commande', 'Non détecté')}")
        
        return resultat
        
    except Exception as e:
        return {"erreur": f"Erreur Vision: {e}"}


def extraire_avec_vision_si_besoin(file_path: str, resultat_actuel: Dict[str, Any]) -> Dict[str, Any]:
    """
    Utilise la Vision UNIQUEMENT si des informations sont manquantes.
    Fusionne les résultats (Vision prime sur l'existant).
    """
    # Vérifier ce qui manque
    objet_manquant = not resultat_actuel.get('objet_commande') or resultat_actuel.get('objet_commande') == 'Non détecté'
    
    # Vérifier les annexes manquantes
    annexes = resultat_actuel.get('annexes', {})
    annexes_manquantes = not any(annexes.values()) if annexes else True
    
    if not objet_manquant and not annexes_manquantes:
        print("   ✅ Toutes les informations sont déjà détectées")
        return resultat_actuel
    
    print("   🔍 Vision: analyse supplémentaire en cours...")
    resultat_vision = analyser_avec_vision(file_path)
    
    if 'erreur' in resultat_vision:
        print(f"   ⚠️ Vision a échoué: {resultat_vision['erreur']}")
        return resultat_actuel
    
    # Fusionner les résultats
    resultat_final = resultat_actuel.copy()
    
    # Objet
    if objet_manquant and resultat_vision.get('objet_commande'):
        resultat_final['objet_commande'] = resultat_vision['objet_commande']
        resultat_final['_source_objet'] = 'vision'
        print(f"   ✅ Vision a trouvé l'objet: {resultat_vision['objet_commande']}")
    
    # Annexes
    if resultat_vision.get('annexes'):
        for cle, valeur in resultat_vision['annexes'].items():
            if valeur and not resultat_final.get('annexes', {}).get(cle):
                resultat_final['annexes'][cle] = valeur
                print(f"   ✅ Vision a trouvé: {cle}")
    
    return resultat_final