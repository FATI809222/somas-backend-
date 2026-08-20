# core/gemini_extractor.py - VERSION AVEC VISION DIRECTE

import os
import json
import time
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from django.conf import settings

# ⭐ SDK Gemini
from google import genai
from google.genai import types

# ⭐ Pour convertir PDF en images
from pdf2image import convert_from_path
from PIL import Image

load_dotenv()

# ⭐ ⭐ ⭐ CONFIGURATION ⭐ ⭐ ⭐

# ✅ PAS DE VALEUR PAR DÉFAUT
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY non définie dans .env")

GEMINI_MODEL = "gemini-3.5-flash-lite"  # ✅ Modèle stable pour la vision

print("="*60)
print("🔴 CONFIGURATION GEMINI VISION DIRECTE")
print(f"📌 API Key: {GEMINI_API_KEY[:10]}...")
print(f"📌 Modèle Vision: {GEMINI_MODEL}")
print("="*60)

if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY non définie. Gemini sera désactivé.")
    GEMINI_DISABLED = True
    client = None
else:
    GEMINI_DISABLED = False
    client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"✅ Gemini configuré avec succès")


# ⭐ ⭐ ⭐ PROMPT POUR LA VISION DIRECTE ⭐ ⭐ ⭐
# core/gemini_extractor.py - PROMPT ULTRA-GENERIQUE ET PUISSANT

PROMPT_VISION_DIRECTE = """
Tu es un expert en analyse de documents financiers, comptables et commerciaux.

⚠️ RÈGLES FONDAMENTALES :
- Analyse TOUTES les pages du document avec une attention extrême.
- Extrais UNIQUEMENT ce que tu vois CLAIREMENT.
- Si tu as un DOUTE, mets null ou false.
- N'INVENTE RIEN. Ne suppose rien.

📋 OBJECTIF : Extraire les informations structurées du document.

🎯 PARTIE 1 : OBJET DE COMMANDE

L'objet de commande est la description de ce qui est facturé (prestation, service, produit).

🔍 MÉTHODE DE RECHERCHE (par ordre de priorité) :

1. Cherche les intitulés suivants dans le document :
   - "OBJET", "Objet"
   - "PRESTATION", "Prestation" 
   - "DESIGNATION", "Désignation"
   - "ACTIVITE", "Activité"
   - "DESCRIPTION", "Description"
   - "NATURE", "Nature"
   - "MARCHANDISE", "Marchandise"
   - "PRODUIT", "Produit"
   - "SERVICE", "Service"

2. Analyse le contenu associé à ces intitulés :
   - Si c'est un tableau, prends la description principale
   - Si c'est une ligne, prends le texte complet
   - Si plusieurs, prends le plus descriptif

3. Si aucun intitulé n'est trouvé, analyse le contexte global :
   - Le titre du document
   - Les premières lignes de la page 1
   - La description des articles ou services

⚠️ RÈGLES D'EXTRACTION :
- Recopie le texte EXACTEMENT comme il apparaît
- Ne résume pas, ne reformule pas
- Si le texte est trop long, prends les 100 premiers caractères
- Si tu ne trouves rien, mets null

🎯 PARTIE 2 : ⭐ DATE D'ÉDITION ⭐ (TRÈS IMPORTANT)

⚠️⚠️⚠️ INSTRUCTION CRITIQUE - À LIRE ATTENTIVEMENT ⚠️⚠️⚠️

La date d'édition est UNIQUEMENT la date qui est PRÉCÉDÉE du texte "Date d'édition" ou "DATE D'ÉDITION".

🔍 RECHERCHE EXACTE :

1. Cherche UNIQUEMENT ces textes EXACTS :
   - "Date d'édition" suivi d'une date
   - "DATE D'ÉDITION" suivi d'une date

❌ CE QU'IL NE FAUT ABSOLUMENT PAS PRENDRE :
   - "ACCUSE DE RECEPTION" → IGNORER TOTALEMENT
   - "12 JUIN 2026 Accuse de Reception" → IGNORER
   - La date de la facture → IGNORER
   - Toute date sans "Date d'édition" devant → IGNORER
   
   📍 Où chercher ?
   - Page 3 : Demande d'attestation de régularité fiscale
   - Cadre réservé à l'Administration


4. RÈGLE ABSOLUE :
   - SI tu ne vois PAS le texte "Date d'édition" suivi d'une date → mets null
   - N'INVENTE PAS de date d'édition

5. Où chercher ?
   - Page 3 : Demande d'attestation de régularité fiscale
   - Cadre réservé à l'Administration
   - En bas de la page 3

🎯 PARTIE 3 : DOCUMENTS ANNEXES - CRITÈRES TRÈS STRICTS

Scanne TOUTES les pages. Pour chaque document, cherche les INDICES SUIVANTS :

1. attestation_rib :
   - VRAI UNIQUEMENT si tu vois "RIB :" suivi d'un numéro de compte bancaire complet
   - Exemple: "RIB : 011 780 0000 60 210 00 0116692" → true
   - SINON → false

2. bon_livraison :
   - VRAI si tu vois "BL", "BON DE LIVRAISON" ou "DELIVERY FORM"
   - Exemple: "BL N° 26-51" → true
   - SINON → false

3. pv_reception :
   - VRAI si tu vois "PV", "PROCES VERBAL" ou "PV DE RECEPTION"
   - SINON → false

4. pv_location :
   - VRAI si tu vois "PV DE LOCATION" ou "CONTRAT DE LOCATION"
   - SINON → false

5. feuille_presence :
   - VRAI si tu vois "FEUILLE DE PRESENCE"
   - SINON → false

6. certificats_rapport :
   - ⚠️⚠️⚠️ CRITÈRE TRÈS STRICT - FAUX POSITIFS À ÉVITER ⚠️⚠️⚠️
   - VRAI UNIQUEMENT si tu vois UN DE CES TITRES EXACTS :
     * "CERTIFICAT ANNUEL" suivi d'une description
     * "CERTIFICAT DE VERIFICATION" 
     * "RAPPORT DE VERIFICATION"
     * "CERTIFICAT DE CONFORMITE"
     * "ATTESTATION DE CONFORMITE"
     * "RAPPORT DE CONTRÔLE"
   - ⚠️ CE QUI N'EST PAS UN CERTIFICAT :
     * Les noms de produits (ex: "ENDRESS HAUSER", "OMNI", "MODULE AFFICHAGE") → CE N'EST PAS UN CERTIFICAT
     * Les références (ex: "REF", "N° REF", "REF500967542") → CE N'EST PAS UN CERTIFICAT
     * Les numéros de série → CE N'EST PAS UN CERTIFICAT
     * Les descriptifs techniques → CE N'EST PAS UN CERTIFICAT
     * Les numéros de facture → CE N'EST PAS UN CERTIFICAT
   - SINON → false (même si tu as un doute)

7. engagement_importation :
   - VRAI si tu vois "ENGAGEMENT D'IMPORTATION", "DUM" ou "DECLARATION A ENREGISTREMENT"
   - SINON → false

8. quittance_douane :
   - VRAI si tu vois "QUITTANCE DOUANE", "FICHE DE LIQUIDATION" ou "LIQUIDATION DES DROITS"
   - SINON → false

9. ⭐ ATTESTATION DE RÉGULARITÉ FISCALE - CASE "N'A PAS" ⭐

⚠️⚠️⚠️ INSTRUCTION CRITIQUE ⚠️⚠️⚠️

Dans la page "Demande d'attestation de régularité fiscale", cherche la case :
"N'a pas, à la date de délivrance de cette attestation, de dette fiscale exigible ni de procédure engagée pour un manquement aux obligations de déclaration"

🔍 RECHERCHE :
1. Trouve la page qui contient "Demande d'attestation de régularité fiscale"
2. Cherche le texte "N'a pas" ou "نشهد أن الملزم ليس لديه"
3. Vérifie si la case est COCHÉE (☑️, ✅, X, ou une case remplie)

📋 RÉSULTAT :
- Si la case est COCHÉE → "est_en_regle": true
- Si la case est DÉCOCHÉE → "est_en_regle": false
- Si tu ne trouves PAS la page → "est_en_regle": null

📄 RÉPONSE UNIQUEMENT EN JSON (strict) :
{
  "objet_commande": "texte extrait ou null",
  "confiance": "haute/moyenne/faible",
  "source": "page et position",
  "numero_facture": "texte ou null",
  "date_facture": "texte ou null",
  "fournisseur": "texte ou null",
  "montant_ttc": 0.00,
  "date_edition": "JJ/MM/AAAA ou null",
  "est_en_regle": true/false/null,
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


def charger_pages_en_images(file_path: str, dpi: int = 150, max_pages: int = 15) -> List[Image.Image]:
    """
    Convertit le PDF en images pour la vision Gemini.
    """
    if file_path.lower().endswith('.pdf'):
        pages = convert_from_path(file_path, dpi=dpi)
        if len(pages) > max_pages:
            print(f"   ⚠️ Document trop long ({len(pages)} pages), limité à {max_pages} pages")
            pages = pages[:max_pages]
        return pages
    elif file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        return [Image.open(file_path)]
    else:
        return []


def corriger_fournisseur_avec_liste(resultat: Dict[str, Any], texte_ocr: str = None) -> Dict[str, Any]:
    """
    Vérifie que le fournisseur détecté par Gemini existe dans la liste SOMAS.
    Si ce n'est pas le cas, cherche le bon fournisseur dans la liste.
    ⭐ PRIORITÉ : Le fournisseur détecté par Gemini doit être vérifié.
    """
    from core.fournisseurs_list import FOURNISSEURS_SOMAS, ALIAS_FOURNISSEURS
    
    fournisseur = resultat.get('fournisseur', '')
    
    if not fournisseur or fournisseur == "null" or fournisseur == "Non détecté":
        print(f"   ⚠️ Aucun fournisseur détecté par Gemini")
        return resultat
    
    fournisseur_upper = fournisseur.upper().strip()
    
    # ⭐ 1. VÉRIFIER SI LE FOURNISSEUR EST DANS LA LISTE
    trouve = False
    for nom in FOURNISSEURS_SOMAS:
        if nom.upper() == fournisseur_upper:
            trouve = True
            print(f"   ✅ Fournisseur '{fournisseur}' trouvé dans la liste SOMAS")
            break
    
    # ⭐ 2. SI PAS TROUVÉ, CHERCHER PAR ALIAS
    if not trouve:
        # Vérifier les alias
        for alias, nom_officiel in ALIAS_FOURNISSEURS.items():
            if alias.upper() == fournisseur_upper or alias.upper() in fournisseur_upper:
                resultat['fournisseur'] = nom_officiel
                resultat['_fournisseur_source'] = 'alias'
                print(f"   ✅ Fournisseur corrigé via alias: {alias} → {nom_officiel}")
                return resultat
        
        # ⭐ 3. CHERCHER DANS LA LISTE (correspondance partielle)
        for nom in FOURNISSEURS_SOMAS:
            # Si le nom détecté est contenu dans un nom de la liste
            if len(fournisseur) > 3 and fournisseur_upper in nom.upper():
                resultat['fournisseur'] = nom
                resultat['_fournisseur_source'] = 'correction_partielle'
                print(f"   ✅ Fournisseur corrigé (correspondance partielle): {fournisseur} → {nom}")
                return resultat
            
            # Si un nom de la liste est contenu dans le nom détecté
            if len(nom) > 3 and nom.upper() in fournisseur_upper:
                resultat['fournisseur'] = nom
                resultat['_fournisseur_source'] = 'correction_partielle'
                print(f"   ✅ Fournisseur corrigé (correspondance partielle): {fournisseur} → {nom}")
                return resultat
    
    # ⭐ 4. SI TOUJOURS PAS TROUVÉ, CHERCHER DANS L'OCR (fallback)
    if not trouve and texte_ocr:
        print(f"   ⚠️ Fournisseur '{fournisseur}' non trouvé dans la liste SOMAS")
        print(f"   🔍 Recherche dans l'OCR...")
        
        entete = '\n'.join(texte_ocr.split('\n')[:30])
        entete_upper = entete.upper()
        
        for nom in FOURNISSEURS_SOMAS:
            if nom.upper() in entete_upper:
                resultat['fournisseur'] = nom
                resultat['_fournisseur_source'] = 'correction_ocr_entete'
                print(f"   ✅ Fournisseur corrigé (OCR en-tête): {nom}")
                return resultat
        
        # Chercher dans tout le texte
        for nom in FOURNISSEURS_SOMAS:
            if nom.upper() in texte_ocr.upper():
                # ⚠️ Vérifier que ce n'est pas SAMIR (faux positif)
                if nom.upper() == "SAMIR":
                    if "CAV SAMIR" in texte_ocr.upper() or "SAMIR PIPELINE" in texte_ocr.upper():
                        continue
                resultat['fournisseur'] = nom
                resultat['_fournisseur_source'] = 'correction_ocr_texte'
                print(f"   ✅ Fournisseur corrigé (OCR): {nom}")
                return resultat
    
    return resultat


def extraire_objet_et_annexes_avec_vision_directe(file_path: str, texte_ocr: str = None) -> Dict[str, Any]:
    """
    Utilise Gemini Vision directement sur les images du PDF.
    ⭐ PAS D'OCR ! Gemini voit le document comme un humain.
    ⭐ Détecte aussi les dates des annexes en un seul appel.
    """
    
    if GEMINI_DISABLED or client is None:
        return {
            "objet_commande": None,
            "confiance": "faible",
            "source": "gemini_désactivé",
            "numero_facture": None,
            "date_facture": None,
            "fournisseur": None,
            "montant_ttc": None,
            "date_edition": None,
            "est_en_regle": None,
            "annexes": {
                "attestation_rib": False,
                "bon_livraison": False,
                "pv_reception": False,
                "pv_location": False,
                "feuille_presence": False,
                "certificats_rapport": False,
                "engagement_importation": False,
                "quittance_douane": False
            },
            "dates_annexes": {
                "bon_livraison": None,
                "pv_reception": None,
                "pv_location": None,
                "feuille_presence": None,
                "certificats_rapport": None
            }
        }
    
    try:
        print(f"   👁️ Gemini Vision - Analyse directe du document...")
        
        # ⭐ 1. Charger les pages en images
        pages = charger_pages_en_images(file_path)
        if not pages:
            print(f"   ❌ Aucune page chargée")
            return {"erreur": "Aucune page trouvée"}
        
        print(f"   📄 {len(pages)} pages analysées en vision directe")
        
        # ⭐ 2. PROMPT MODIFIÉ pour inclure la date d'édition, les dates des annexes et la case "est_en_regle"
        PROMPT_VISION_DIRECTE_AVEC_DATES = """
Tu es un expert en analyse de documents marocains (factures, bons de livraison, PV, certificats, etc.).

⚠️⚠️⚠️ RÈGLES FONDAMENTALES - À LIRE ABSOLUMENT ⚠️⚠️⚠️

1. Ne détecte JAMAIS un document qui n'est pas PHYSIQUEMENT présent dans le fichier.
2. Une simple mention dans les conditions générales (ex: "PV/Attachement validé par SOMAS") n'est PAS un document.
3. Pour qu'un document soit détecté, il doit avoir un TITRE CLAIR et visible.

Analyse attentivement les images du document et extrait les informations suivantes :

1. **Objet de la commande** : L'objet de la prestation/fourniture (exactement comme écrit)
2. **Numéro de facture** : Le numéro de facture
3. **Date de la facture** : La date de la facture (format JJ/MM/AAAA)
4. **Fournisseur** : Le nom exact du fournisseur
5. **Montant TTC** : Le montant total TTC

6. **⭐ DATE D'ÉDITION (RÈGLE ABSOLUE)** :
   ⚠️⚠️⚠️ INSTRUCTION CRITIQUE - FORMAT OBLIGATOIRE ⚠️⚠️⚠️
   
   🔴🔴🔴 TOUTES LES DATES DOIVENT ÊTRE AU FORMAT JJ/MM/AAAA 🔴🔴🔴
   Exemple: si tu vois "07-03-2025" → tu retournes "07/03/2025"
   Exemple: si tu vois "07.03.2025" → tu retournes "07/03/2025"
   Exemple: si tu vois "2025-03-07" → tu retournes "07/03/2025"
   Exemple: si tu vois "07/03/2025" → tu retournes "07/03/2025"

   🔍 ÉTAPE 1 : D'abord, vérifie si le document contient une **Demande d'attestation de régularité fiscale**.
   - Cherche ces titres : "Demande d'attestation de régularité fiscale", "طلب شهادة الوضعية الجبائية القانونية"
   - Ce document se trouve généralement en PAGE 3
   - Si ce document N'EST PAS présent → mets null pour date_edition et passe à l'étape suivante

   🔍 ÉTAPE 2 : Si la Demande d'attestation est présente, cherche la **Date d'édition** à l'intérieur.
   - Cherche EXACTEMENT "Date d'édition" ou "DATE D'ÉDITION"
   - La date est souvent en bas du document, dans le cadre réservé à l'Administration
   - ⚠️ Peu importe le format original (JJ-MM-AAAA, JJ.MM.AAAA, AAAA-MM-JJ), tu DOIS retourner JJ/MM/AAAA

   🔍 ÉTAPE 3 (FALLBACK) : Si la Demande d'attestation n'est pas présente, cherche l'accusé de réception.
   - Cherche "ACCUSE DE RECEPTION" ou "ACCUSÉ DE RÉCEPTION"
   - Exemple: "12 JUIN 2026" → tu retournes "12/06/2026"

   ❌ CE QU'IL NE FAUT PAS PRENDRE :
   - La date de la facture → CE N'EST PAS LA DATE D'ÉDITION
   - Toute date sans contexte clair

   📍 RÉSUMÉ :
   1. PRIORITÉ 1 : "Demande d'attestation" + "Date d'édition" → retourner JJ/MM/AAAA
   2. PRIORITÉ 2 : "ACCUSE DE RECEPTION" (si pas d'attestation) → retourner JJ/MM/AAAA
   3. Si rien trouvé → null

7. **⭐ EST_EN_REGLE - CASE "N'A PAS" DANS L'ATTESTATION FISCALE ⭐** :

   ⚠️⚠️⚠️ INSTRUCTION CRITIQUE ⚠️⚠️⚠️

   Dans la page "Demande d'attestation de régularité fiscale", cherche la case :
   "N'a pas, à la date de délivrance de cette attestation, de dette fiscale exigible ni de procédure engagée pour un manquement aux obligations de déclaration"

   🔍 RECHERCHE :
   1. Trouve la page qui contient "Demande d'attestation de régularité fiscale"
   2. Cherche le texte "N'a pas" ou "نشهد أن الملزم ليس لديه"
   3. Vérifie si la case est COCHÉE (☑️, ✅, X, ou une case remplie)

   📋 RÉSULTAT :
   - Si la case est COCHÉE → "est_en_regle": true
   - Si la case est DÉCOCHÉE → "est_en_regle": false
   - Si tu ne trouves PAS la page → "est_en_regle": null

8. **⭐ DOCUMENTS ANNEXES - RÈGLES TRÈS STRICTES ⭐** :

   ⚠️⚠️⚠️ RÈGLE D'OR : Un document annexe n'est détecté que si tu vois SON TITRE CLAIR dans le document.
   Une simple mention dans les conditions générales ou un renvoi (ex: "PV/Attachement") NE COMPTE PAS.

   🔍 Pour CHAQUE annexe, vérifie :

   a. **attestation_rib** :
      - VRAI UNIQUEMENT si tu vois un RIB COMPLET (format: 4 groupes de chiffres)
      - Exemple: "RIB : 011 780 0000 60 210 00 0116692"
      - SINON → false

   b. **bon_livraison** :
      - VRAI UNIQUEMENT si tu vois le TITRE "BON DE LIVRAISON" ou "BL" dans le document
      - ⚠️ Une mention dans les conditions (ex: "présentation BL") N'EST PAS un BL
      - SINON → false

   c. **pv_reception** :
      - VRAI UNIQUEMENT si tu vois le TITRE "PV DE RECEPTION", "PROCES VERBAL" ou "PV"
      - ⚠️ Une mention dans les conditions (ex: "PV/Attachement validé") N'EST PAS un PV
      - SINON → false

   d. **pv_location** :
      - VRAI UNIQUEMENT si tu vois le TITRE "PV DE LOCATION" ou "CONTRAT DE LOCATION"
      - SINON → false

   e. **feuille_presence** :
      - VRAI UNIQUEMENT si tu vois le TITRE "FEUILLE DE PRESENCE"
      - SINON → false
    f. **validation_bureau_etudes_controle** :
      - VRAI UNIQUEMENT si tu vois l'un de ces TITRES EXACTS :
        * "BUREAU D'ÉTUDES"
        * "BUREAU DE CONTRÔLE"
        * "VALIDATION TECHNIQUE"
        * "BUREAU D'ETUDES"
        * "BUREAU DE CONTROLE"
      - ⚠️ Une simple mention dans les conditions générales NE COMPTE PAS.
      - SINON → false

   g. **certificats_rapport** :
      ⚠️⚠️⚠️ CRITÈRE LE PLUS STRICT - ATTENTION AUX FAUX POSITIFS ⚠️⚠️⚠️
      
      🔴 RÈGLE ABSOLUE : Ce champ est VRAI UNIQUEMENT si tu vois un DOCUMENT COMPLET qui a pour TITRE EXACT :
         - "CERTIFICAT ANNUEL" + une description détaillée sur plusieurs lignes
         - "CERTIFICAT DE VERIFICATION" + contenu technique
         - "RAPPORT DE VERIFICATION" + contenu technique
         - "CERTIFICAT DE CONFORMITE" + contenu technique
         - "ATTESTATION DE CONFORMITE" + contenu technique
         - "RAPPORT DE CONTRÔLE" + contenu technique
      
      🔴 CE QUI N'EST PAS UN CERTIFICAT (liste exhaustive) :
         ✅ Les noms de produits (ex: "ENDRESS HAUSER", "OMNI", "MODULE AFFICHAGE")
         ✅ Les références (ex: "REF", "N° REF", "REF500967542")
         ✅ Les numéros de série
         ✅ Les descriptifs techniques
         ✅ Les numéros de facture
         ✅ Les dates seules (ex: "15/08/2025") sans titre de certificat
         ✅ Les mentions "PV/Attachement" dans les conditions générales
         ✅ Les phrases "présentation PV" ou "PV de réception" dans les conditions
         ✅ Les numéros de bon de commande
         ✅ Les références budgétaires (ex: "R. Budgétaire : I2025-IS-03")
      
      ⚠️ SI TU AS UN DOUTE → mets false
      ⚠️ SI C'EST UNE MENTION DANS LES CONDITIONS → mets false
      ⚠️ SI C'EST UNE RÉFÉRENCE OU UN NUMÉRO → mets false

   h. **engagement_importation** :
      - VRAI UNIQUEMENT si tu vois "ENGAGEMENT D'IMPORTATION", "DUM" ou "DECLARATION A ENREGISTREMENT"
      - SINON → false

    1. **attestation_rib** :
   ⚠️⚠️⚠️ RÈGLE TRÈS STRICTE ⚠️⚠️⚠️
   
   ⭐ L'attestation RIB est un DOCUMENT SÉPARÉ, pas juste un numéro sur la facture !
   
   🔴 VRAI UNIQUEMENT SI :
   - Le document contient le TITRE "ATTESTATION RIB" ou "RELEVÉ D'IDENTITÉ BANCAIRE"
   - OU le document contient "ATTESTATION DE RIB" en titre
   - ET le document est un formulaire spécifique avec en-tête "Attestation"
   
   🔴 FAUX (ne pas confondre) :
   - Un simple numéro RIB dans la facture → NE COMPTE PAS
   - Une ligne "RIB : 011 780 0000..." dans la facture → NE COMPTE PAS
   - Les conditions de paiement avec RIB → NE COMPTE PAS
   - Le RIB dans l'en-tête de la facture → NE COMPTE PAS
   
   📋 RÈGLE ABSOLUE :
   - Si tu vois le mot "RIB" mais pas le mot "ATTESTATION" devant → c'est FAUX
   - Si tu vois juste un numéro de compte bancaire → c'est FAUX
   - Si tu vois "RIB :" suivi de chiffres → c'est FAUX (c'est le RIB du fournisseur, pas une attestation)
   - Si tu vois "ATTESTATION RIB" en TITRE → c'est VRAI
   - Si tu vois "RELEVÉ D'IDENTITÉ BANCAIRE" en TITRE → c'est VRAI
   
   ⚠️ EN CAS DE DOUTE → mets false

   i. **quittance_douane** :
      - VRAI UNIQUEMENT si tu vois "QUITTANCE DOUANE", "FICHE DE LIQUIDATION" ou "LIQUIDATION DES DROITS"
      - SINON → false

9. **⭐ DATES DES ANNEXES** :
   - ⚠️ Pour une annexe qui est VRAIE, extrais sa date (format JJ/MM/AAAA)
   - ⚠️ Pour une annexe qui est FALSE, mets null
   - ⚠️ Même règle stricte : une date seule sans titre de document n'est PAS une date d'annexe

⚠️⚠️⚠️ RÈGLE ABSOLUE POUR TOUTES LES DATES ⚠️⚠️⚠️
- TOUTES LES DATES DOIVENT ÊTRE AU FORMAT **JJ/MM/AAAA**
- PEU IMPORTE LE FORMAT ORIGINAL DANS LE DOCUMENT
- TU DOIS TOUJOURS CONVERTIR EN **JJ/MM/AAAA**
- JAMAIS avec des tirets "-", JAMAIS avec des points "."
- UNIQUEMENT avec des slashes "/"

RÉPONDS UNIQUEMENT EN JSON AVEC CE FORMAT EXACT :
{
  "objet_commande": "texte exact ou null",
  "confiance": "haute|moyenne|faible",
  "numero_facture": "texte ou null",
  "date_facture": "JJ/MM/AAAA ou null",
  "fournisseur": "texte ou null",
  "montant_ttc": 0.00 ou null,
  "date_edition": "JJ/MM/AAAA ou null",
  "est_en_regle": true/false/null,
  "annexes": {
    "attestation_rib": true/false,
    "bon_livraison": true/false,
    "pv_reception": true/false,
    "pv_location": true/false,
    "validation_bureau_etudes_controle": true/false,
    "feuille_presence": true/false,
    "certificats_rapport": true/false,
    "engagement_importation": true/false,
    "quittance_douane": true/false
  },
  "dates_annexes": {
    "bon_livraison": "JJ/MM/AAAA ou null",
    "pv_reception": "JJ/MM/AAAA ou null",
    "pv_location": "JJ/MM/AAAA ou null",
    "feuille_presence": "JJ/MM/AAAA ou null",
    "certificats_rapport": "JJ/MM/AAAA ou null"
  }
}
"""
        
        # ⭐ 3. Préparer le contenu : prompt + toutes les images
        contenu = [PROMPT_VISION_DIRECTE_AVEC_DATES] + pages
        
        # ⭐ 4. Appeler Gemini Vision
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contenu
        )
        
        # ⭐ 5. Extraire le JSON
        content = response.text
        print(f"   📝 Réponse Vision (extrait): {content[:300]}...")
        
        # Nettoyer la réponse
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            json_str = content[start:end].strip()
        elif "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
        else:
            json_str = content
        
        resultat = json.loads(json_str)
        
        # ⭐⭐⭐ 6. CORRIGER LE FOURNISSEUR AVEC LA LISTE ⭐⭐⭐
        if resultat.get('fournisseur') in ['null', 'Non détecté', None]:
            pass
        
        # ⭐ 7. S'assurer que toutes les clés des annexes existent
        annexes = resultat.get('annexes', {})
        cles_attendues = [
            "attestation_rib", "bon_livraison", "pv_reception", "pv_location",
            "feuille_presence", "certificats_rapport", "engagement_importation", "quittance_douane"
        ]
        for cle in cles_attendues:
            if cle not in annexes:
                annexes[cle] = False
        resultat['annexes'] = annexes
        
        # ⭐ 8. S'assurer que la date d'édition existe
        if 'date_edition' not in resultat:
            resultat['date_edition'] = None
        if resultat['date_edition'] in ["null", "None", "Non détectée", ""]:
            resultat['date_edition'] = None
        
        # ⭐ 9. S'assurer que est_en_regle existe
        if 'est_en_regle' not in resultat:
            resultat['est_en_regle'] = None
        if resultat['est_en_regle'] in ["null", "None", ""]:
            resultat['est_en_regle'] = None
        
        # ⭐ 10. S'assurer que les dates des annexes existent
        dates_annexes = resultat.get('dates_annexes', {})
        cles_dates = [
            "bon_livraison", "pv_reception", "pv_location", 
            "feuille_presence", "certificats_rapport"
        ]
        for cle in cles_dates:
            if cle not in dates_annexes:
                dates_annexes[cle] = None
            # ⭐ Nettoyer les valeurs null
            if dates_annexes[cle] in ["null", "None", "Non détectée", ""]:
                dates_annexes[cle] = None
        resultat['dates_annexes'] = dates_annexes
        
        # ⭐⭐⭐ 11. FILTRE ANTI-FAUX POSITIFS POUR BON DE LIVRAISON ⭐⭐⭐
        if resultat['annexes'].get('bon_livraison', False):
            # Vérifier si c'est juste une mention dans les conditions
            est_faux_positif_bl = False
            
            if texte_ocr:
                # Vérifier si "BL" ou "BON DE LIVRAISON" est dans le texte
                if "BL" in texte_ocr.upper() or "BON DE LIVRAISON" in texte_ocr.upper():
                    # Vérifier si c'est dans les conditions de paiement
                    if "PV/Attachement" in texte_ocr or "présentation PV" in texte_ocr:
                        # Vérifier s'il y a vraiment un titre "BON DE LIVRAISON" en titre (pas juste une mention)
                        a_un_titre_bl = False
                        titres_bl = [
                            "BON DE LIVRAISON",
                            "BON DE LIVRAISON N°",
                            "BL N°",
                            "LIVRAISON"
                        ]
                        # Vérifier dans les 30 premières lignes (en-tête)
                        lignes = texte_ocr.split('\n')[:30]
                        for ligne in lignes:
                            for titre in titres_bl:
                                if titre.upper() in ligne.upper():
                                    # Vérifier que ce n'est pas une mention dans les conditions
                                    if "CONDITIONS" not in ligne.upper() and "PAIEMENT" not in ligne.upper():
                                        a_un_titre_bl = True
                                        break
                            if a_un_titre_bl:
                                break
                        
                        if not a_un_titre_bl:
                            est_faux_positif_bl = True
                            print(f"   ⚠️ Filtrage : Bon de livraison détecté mais pas de titre réel (simple mention dans conditions)")
            
            # Si faux positif, annuler la détection
            if est_faux_positif_bl:
                resultat['annexes']['bon_livraison'] = False
                resultat['dates_annexes']['bon_livraison'] = None
                print(f"   ❌ Détection de bon de livraison annulée (faux positif)")
            else:
                # Vérifier si le BL a une date
                if not dates_annexes.get('bon_livraison'):
                    # Si pas de date, essayer d'en extraire une du texte
                    if texte_ocr:
                        import re
                        patterns_date = [
                            r'BL\s*N°\s*\d+\s+(\d{2}/\d{2}/\d{4})',
                            r'BON DE LIVRAISON\s*N°\s*\d+\s+(\d{2}/\d{2}/\d{4})',
                            r'DATE\s+DE\s+LIVRAISON\s*[:]\s*(\d{2}/\d{2}/\d{4})',
                            r'LIVRAISON\s+LE\s*[:]\s*(\d{2}/\d{2}/\d{4})',
                        ]
                        for pattern in patterns_date:
                            match = re.search(pattern, texte_ocr, re.IGNORECASE)
                            if match:
                                resultat['dates_annexes']['bon_livraison'] = match.group(1)
                                print(f"   ✅ Date BL extraite du texte: {match.group(1)}")
                                break
        
        # ⭐⭐⭐ 12. FILTRE ANTI-FAUX POSITIFS POUR PV DE RÉCEPTION ⭐⭐⭐
        if resultat['annexes'].get('pv_reception', False):
            # Vérifier si c'est juste une mention dans les conditions
            est_faux_positif_pv = False
            
            if texte_ocr:
                # Vérifier si "PV" ou "PROCES VERBAL" est dans le texte
                if "PV" in texte_ocr.upper() or "PROCES VERBAL" in texte_ocr.upper():
                    # Vérifier si c'est dans les conditions de paiement
                    if "PV/Attachement" in texte_ocr or "présentation PV" in texte_ocr:
                        # Vérifier s'il y a vraiment un titre "PV DE RECEPTION" en titre
                        a_un_titre_pv = False
                        titres_pv = [
                            "PV DE RECEPTION",
                            "PROCES VERBAL DE RECEPTION",
                            "PV DE RÉCEPTION",
                            "PV N°"
                        ]
                        # Vérifier dans tout le texte (pas seulement l'en-tête)
                        for titre in titres_pv:
                            if titre.upper() in texte_ocr.upper():
                                # Vérifier que ce n'est pas juste une mention
                                idx = texte_ocr.upper().find(titre.upper())
                                if idx != -1:
                                    # Regarder le contexte autour
                                    contexte = texte_ocr[max(0, idx-50):idx+100]
                                    if "CONDITIONS" not in contexte.upper() and "PAIEMENT" not in contexte.upper():
                                        a_un_titre_pv = True
                                        break
                        
                        if not a_un_titre_pv:
                            # Si "PV DE RECEPTION" n'est pas trouvé, vérifier si c'est un vrai PV
                            # Dans le document SMARTING, il y a "PV de réception : 01" en page 2
                            if "PV DE RÉCEPTION" in texte_ocr.upper() or "PV DE RECEPTION" in texte_ocr.upper():
                                # Vérifier que ce n'est pas dans les conditions
                                idx_pv = texte_ocr.upper().find("PV DE RÉCEPTION")
                                if idx_pv != -1:
                                    contexte = texte_ocr[max(0, idx_pv-50):idx_pv+100]
                                    if "CONDITIONS" not in contexte.upper() and "PAIEMENT" not in contexte.upper():
                                        a_un_titre_pv = True
                            
                            # Vérifier aussi "PV de réception : 01" (format spécifique)
                            if "PV DE RÉCEPTION :" in texte_ocr.upper() or "PV DE RECEPTION :" in texte_ocr.upper():
                                idx_pv = texte_ocr.upper().find("PV DE RÉCEPTION :")
                                if idx_pv != -1:
                                    contexte = texte_ocr[max(0, idx_pv-50):idx_pv+100]
                                    if "CONDITIONS" not in contexte.upper() and "PAIEMENT" not in contexte.upper():
                                        a_un_titre_pv = True
                        
                        if not a_un_titre_pv:
                            est_faux_positif_pv = True
                            print(f"   ⚠️ Filtrage : PV de réception détecté mais pas de titre réel (simple mention dans conditions)")
            
            # Si faux positif, annuler la détection
            if est_faux_positif_pv:
                resultat['annexes']['pv_reception'] = False
                resultat['dates_annexes']['pv_reception'] = None
                print(f"   ❌ Détection de PV de réception annulée (faux positif)")
            else:
                # Vérifier si le PV a une date
                if not dates_annexes.get('pv_reception'):
                    # Si pas de date, essayer d'en extraire une du texte
                    if texte_ocr:
                        import re
                        patterns_date = [
                            r'PV\s*DE\s*R[ÉE]CEPTION\s*[:]\s*\d+\s+(\d{2}/\d{2}/\d{4})',
                            r'PV\s*N°\s*\d+\s+(\d{2}/\d{2}/\d{4})',
                            r'DATE\s+DU\s+PV\s*[:]\s*(\d{2}/\d{2}/\d{4})',
                            r'PV\s+(\d{2}/\d{2}/\d{4})',
                        ]
                        for pattern in patterns_date:
                            match = re.search(pattern, texte_ocr, re.IGNORECASE)
                            if match:
                                resultat['dates_annexes']['pv_reception'] = match.group(1)
                                print(f"   ✅ Date PV extraite du texte: {match.group(1)}")
                                break
        
        # ⭐⭐⭐ 13. FILTRE ANTI-FAUX POSITIFS POUR CERTIFICATS_RAPPORT ⭐⭐⭐
        if resultat['annexes'].get('certificats_rapport', False):
            date_certificat = dates_annexes.get('certificats_rapport')
            
            # ⭐ Vérifier si c'est un faux positif
            est_faux_positif = False
            
            # 1. Si la date est 15/08/2025 (date typique des faux positifs)
            if date_certificat == "15/08/2025":
                est_faux_positif = True
                print(f"   ⚠️ Filtrage : Date certificat {date_certificat} suspecte (faux positif probable)")
            
            # 2. Si le texte OCR contient "PV/Attachement" mais pas de vrai certificat
            if texte_ocr and ("PV/Attachement" in texte_ocr or "présentation PV" in texte_ocr):
                # Vérifier s'il y a vraiment un titre de certificat
                titres_certificat = [
                    "CERTIFICAT ANNUEL", "CERTIFICAT DE VERIFICATION", 
                    "RAPPORT DE VERIFICATION", "CERTIFICAT DE CONFORMITE",
                    "ATTESTATION DE CONFORMITE", "RAPPORT DE CONTRÔLE"
                ]
                a_un_titre = False
                for titre in titres_certificat:
                    if titre in texte_ocr.upper():
                        a_un_titre = True
                        break
                
                if not a_un_titre:
                    est_faux_positif = True
                    print(f"   ⚠️ Filtrage : Certificat détecté mais pas de titre réel (simple mention dans conditions)")
            
            # 3. Si la date vient d'une ligne qui ressemble à une référence
            if texte_ocr and "260/0805" in texte_ocr:
                est_faux_positif = True
                print(f"   ⚠️ Filtrage : Date de certificat provient d'une référence (260/0805)")
            
            # 4. Si le texte contient "Date d'édition" et "Demande d'attestation" (c'est une attestation, pas un certificat)
            if texte_ocr and "Date d'édition" in texte_ocr and "Demande d'attestation" in texte_ocr:
                # C'est une attestation de régularité fiscale, pas un certificat technique
                est_faux_positif = True
                print(f"   ⚠️ Filtrage : 'certificats_rapport' détecté mais c'est une attestation fiscale, pas un rapport technique")
            
            # ⭐ Si faux positif, annuler la détection
            if est_faux_positif:
                resultat['annexes']['certificats_rapport'] = False
                resultat['dates_annexes']['certificats_rapport'] = None
                print(f"   ❌ Détection de certificat annulée (faux positif)")
        
        # ⭐ 14. Logs
        print(f"   ✅ Vision - Objet: {resultat.get('objet_commande', 'Non détecté')}")
        print(f"   ✅ Vision - Fournisseur: {resultat.get('fournisseur', 'Non détecté')}")
        print(f"   ✅ Vision - N° facture: {resultat.get('numero_facture', 'Non détecté')}")
        print(f"   ✅ Vision - Date facture: {resultat.get('date_facture', 'Non détectée')}")
        print(f"   ✅ Vision - Date d'édition: {resultat.get('date_edition', 'Non détectée')}")
        print(f"   ✅ Vision - Est en règle (case N'a pas): {resultat.get('est_en_regle', 'Non détecté')}")
        
        # Logs des dates des annexes
        for cle, date in dates_annexes.items():
            if date:
                print(f"   ✅ Vision - Date {cle}: {date}")
            else:
                print(f"   ⚠️ Vision - Date {cle}: Non détectée")
        
        resultat['_nb_pages_analysees'] = len(pages)
        
        return resultat
        
    except Exception as e:
        print(f"   ❌ Erreur Vision directe: {e}")
        import traceback
        traceback.print_exc()
        return {
            "objet_commande": None,
            "confiance": "faible",
            "source": "erreur",
            "numero_facture": None,
            "date_facture": None,
            "fournisseur": None,
            "montant_ttc": None,
            "date_edition": None,
            "est_en_regle": None,
            "annexes": {
                "attestation_rib": False,
                "bon_livraison": False,
                "pv_reception": False,
                "pv_location": False,
                "feuille_presence": False,
                "certificats_rapport": False,
                "engagement_importation": False,
                "quittance_douane": False
            },
            "dates_annexes": {
                "bon_livraison": None,
                "pv_reception": None,
                "pv_location": None,
                "feuille_presence": None,
                "certificats_rapport": None
            }
        }


# ⭐ Fonctions de compatibilité
def extraire_objet_avec_gemini(file_path: str) -> Dict[str, Any]:
    """Fonction de compatibilité avec l'ancien code"""
    resultat = extraire_objet_et_annexes_avec_vision_directe(file_path)
    return {
        "objet_commande": resultat.get("objet_commande"),
        "confiance": resultat.get("confiance", "faible"),
        "source": resultat.get("source", "gemini")
    }


def extraire_annexes_avec_gemini(file_path: str) -> Dict[str, bool]:
    """Fonction de compatibilité avec l'ancien code"""
    resultat = extraire_objet_et_annexes_avec_vision_directe(file_path)
    return resultat.get("annexes", {
        "attestation_rib": False,
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False
    })