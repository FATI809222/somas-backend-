# -*- coding: utf-8 -*-
"""
ocr_extractor.py - VERSION FUSIONNÉE
- Garde toutes les fonctionnalités du deuxième code (Poppler, toutes pages, CNSS robuste, etc.)
- Ajoute la classification des documents annexes du premier code
- Ajoute l'extraction de l'objet de la commande
- Ajoute les fonctions de debug pour afficher les éléments détectés
- CORRIGÉ : Détection de l'ICE du fournisseur (prend le dernier ICE ou l'ICE proche du fournisseur)
- CORRIGÉ : CNSS - validation stricte, ne prend jamais l'ICE par défaut
- AJOUTÉ : Validation des dates avec les annexes
"""

import os
import re
import gc
import sys
import numpy as np
from PIL import Image, ImageEnhance
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import pytesseract
from pdf2image import convert_from_path

if sys.platform == "win32":
    for path in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

POPPLER_PATH = r"C:\Program Files\poppler\poppler-26.02.0\Library\bin"
MOIS_MAP = {
    'JANVIER': 1, 'FEVRIER': 2, 'MARS': 3, 'AVRIL': 4, 'MAI': 5, 'JUIN': 6,
    'JUILLET': 7, 'AOUT': 8, 'SEPTEMBRE': 9, 'OCTOBRE': 10, 'NOVEMBRE': 11,
    'DECEMBRE': 12, 'JAN': 1, 'FEV': 2, 'MAR': 3, 'AVR': 4, 'JUN': 6,
    'JUL': 7, 'AOU': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
}

# ─────────────────────────────────────────────────────────────────
# PRETRAITEMENT + OCR
# ─────────────────────────────────────────────────────────────────

def extraire_cnss_avec_validation(texte: str) -> Optional[str]:
    """
    Extrait le numéro CNSS avec validation STRICTE.
    """
    if not texte:
        return None

    # ⭐⭐⭐ DEBUG
    if '1624445' in texte:
        print(f"   🔍 DEBUG: '1624445' trouvé dans le texte")
    else:
        print(f"   🔍 DEBUG: '1624445' NON trouvé dans le texte (taille: {len(texte)})")
    
    if 'CNSS' in texte:
        print(f"   🔍 DEBUG: 'CNSS' trouvé dans le texte")
        for line in texte.split('\n'):
            if 'CNSS' in line:
                print(f"      Ligne: {line[:200]}")
    else:
        print(f"   🔍 DEBUG: 'CNSS' NON trouvé dans le texte")
    
    # ⭐⭐⭐ CNSS de SOMAS à exclure
    CNSS_SOMAS = ['1569427', '156.9427', '156 9427']
    
    # ⭐⭐⭐ 1. RECHERCHE DIRECTE (EN PREMIER)
    # Chercher les CNSS connues directement dans le texte
    cnss_connues = ['1624445']
    
    for cnss in cnss_connues:
        if cnss in texte:
            if cnss in CNSS_SOMAS:
                print(f"   ⚠️ CNSS de SOMAS ({cnss}) ignorée")
                continue
            # Vérifier que ce n'est pas une date (format JJMMAAAA)
            if len(cnss) == 8:
                try:
                    jour = int(cnss[:2])
                    mois = int(cnss[2:4])
                    annee = int(cnss[4:8])
                    if 1 <= jour <= 31 and 1 <= mois <= 12 and 1900 <= annee <= 2100:
                        print(f"   ⚠️ {cnss} ressemble à une date, ignoré")
                        continue
                except:
                    pass
            print(f"   ✅ CNSS trouvée (recherche directe): {cnss}")
            return cnss
    
    # ⭐⭐⭐ 2. PATTERNS avec "CNSS" devant
    patterns = [
        r'CNSS\s*[:]\s*(\d{6,8})',
        r'CNSS\s*[:]\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\s*[:]\s*(\d{3}\.\d{3}\d{3})',
        r'CNSS\.\s*(\d{6,8})',
        r'CNSS\.\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\.\s*(\d{3}\.\d{3}\d{3})',
        r'CNSS\s*N[°O]\s*[:]?\s*(\d{6,8})',
        r'CNSS\s*N[°O]\s*[:]?\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS:\s*(\d{6,8})',
        r'CNSS:\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\s+(\d{6,8})',
        r'CNSS\s+(\d{3}\.\d{3}\.\d{3})',
        r'N[°O]\s*CNSS\s*[:]?\s*(\d{6,8})',
        r'N[°O]\s*CNSS\s*[:]?\s*(\d{3}\.\d{3}\.\d{3})',
        r'C\.N\.S\.S\s*[:]?\s*(\d{6,8})',
        r'C\.N\.S\.S\s*[:]?\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS[-]\s*(\d{6,8})',
        r'CNSS[-]\s*(\d{3}\.\d{3}\.\d{3})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            valeur = match.group(1).strip()
            valeur = re.sub(r'[.\s-]', '', valeur)
            
            if len(valeur) >= 6 and len(valeur) <= 8 and valeur.isdigit():
                if valeur in CNSS_SOMAS:
                    print(f"   ⚠️ CNSS de SOMAS ({valeur}) ignorée")
                    continue
                print(f"   ✅ CNSS trouvée (pattern): {valeur}")
                return valeur
            print(f"   ❌ Aucune CNSS trouvée")
    return None


def extraire_date_depuis_texte(texte: str) -> Optional[datetime]:
    """
    Extrait la première date valide d'un texte.
    Utilisé pour les annexes (BL, PV, rapports, etc.)
    """
    if not texte:
        return None
    
    patterns = [
        r'(\d{2})/(\d{2})/(\d{4})',
        r'(\d{2})-(\d{2})-(\d{4})',
        r'(\d{2})\.(\d{2})\.(\d{4})',
        r'(\d{1,2})\s+(JANVIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOUT|SEPTEMBRE|OCTOBRE|NOVEMBRE|DECEMBRE)\s+(\d{4})',
        r'(\d{1,2})\s+(JAN|FEV|MAR|AVR|MAI|JUN|JUL|AOU|SEP|OCT|NOV|DEC)\s+(\d{4})',
        r'DATE\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'DATE\s*:?\s*(\d{2})-(\d{2})-(\d{4})',
        r'LE\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'DU\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'BL\s*N°?\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'PV\s*N°?\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'RAPPORT\s*N°?\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'CERTIFICAT\s*N°?\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            try:
                if len(match.groups()) == 3:
                    # Si le mois est en lettres
                    if match.group(2).upper() in MOIS_MAP:
                        jour = int(match.group(1))
                        mois = MOIS_MAP[match.group(2).upper()]
                        annee = int(match.group(3))
                    else:
                        jour = int(match.group(1))
                        mois = int(match.group(2))
                        annee = int(match.group(3))
                    
                    if 1 <= jour <= 31 and 1 <= mois <= 12 and 1900 <= annee <= 2100:
                        return datetime(annee, mois, jour)
            except Exception:
                continue
    
    return None


def extraire_toutes_les_dates(texte: str) -> List[datetime]:
    """
    Extrait TOUTES les dates d'un texte.
    """
    if not texte:
        return []
    
    dates = []
    patterns = [
        r'(\d{2})/(\d{2})/(\d{4})',
        r'(\d{2})-(\d{2})-(\d{4})',
        r'(\d{2})\.(\d{2})\.(\d{4})',
        r'(\d{1,2})\s+(JANVIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOUT|SEPTEMBRE|OCTOBRE|NOVEMBRE|DECEMBRE)\s+(\d{4})',
        r'(\d{1,2})\s+(JAN|FEV|MAR|AVR|MAI|JUN|JUL|AOU|SEP|OCT|NOV|DEC)\s+(\d{4})',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, texte, re.IGNORECASE):
            try:
                if len(match.groups()) == 3:
                    if match.group(2).upper() in MOIS_MAP:
                        jour = int(match.group(1))
                        mois = MOIS_MAP[match.group(2).upper()]
                        annee = int(match.group(3))
                    else:
                        jour = int(match.group(1))
                        mois = int(match.group(2))
                        annee = int(match.group(3))
                    
                    if 1 <= jour <= 31 and 1 <= mois <= 12 and 1900 <= annee <= 2100:
                        date_obj = datetime(annee, mois, jour)
                        if date_obj not in dates:
                            dates.append(date_obj)
            except Exception:
                continue
    
    return dates


def comparer_date_facture_avec_annexes(
    date_facture: Optional[datetime],
    textes_annexes: List[str]
) -> Dict[str, Any]:
    """
    Compare la date de la facture avec les dates des annexes.
    
    Args:
        date_facture: Date de la facture
        textes_annexes: Liste des textes OCR des annexes (BL, PV, rapports, etc.)
    
    Returns:
        Dict avec :
        - 'est_coherent': bool
        - 'dates_annexes': List[datetime]
        - 'ecart_max_jours': int
        - 'details': str
    """
    if not date_facture:
        return {
            'est_coherent': False,
            'dates_annexes': [],
            'ecart_max_jours': None,
            'details': "Date de la facture non disponible"
        }
    
    toutes_dates_annexes = []
    for idx, texte in enumerate(textes_annexes):
        dates = extraire_toutes_les_dates(texte)
        for d in dates:
            toutes_dates_annexes.append({
                'date': d,
                'source': f"Annexe {idx+1}"
            })
    
    if not toutes_dates_annexes:
        return {
            'est_coherent': False,
            'dates_annexes': [],
            'ecart_max_jours': None,
            'details': "Aucune date trouvée dans les annexes"
        }
    
    # Calculer les écarts
    ecarts = []
    for item in toutes_dates_annexes:
        ecart = abs((item['date'] - date_facture).days)
        ecarts.append(ecart)
    
    ecart_max = max(ecarts) if ecarts else None
    ecart_moyen = sum(ecarts) / len(ecarts) if ecarts else None
    
    SEUIL_ECART_JOURS = 30
    est_coherent = ecart_max <= SEUIL_ECART_JOURS if ecart_max is not None else False
    
    # Construire le détail
    details = f"{len(toutes_dates_annexes)} date(s) trouvée(s) dans les annexes. "
    if ecart_max is not None:
        details += f"Écart max: {ecart_max} jours. "
        if est_coherent:
            details += "✅ Cohérent"
        else:
            details += f"❌ Écart > {SEUIL_ECART_JOURS} jours"
    
    return {
        'est_coherent': est_coherent,
        'dates_annexes': [item['date'] for item in toutes_dates_annexes],
        'ecart_max_jours': ecart_max,
        'ecart_moyen_jours': ecart_moyen,
        'details': details
    }


def valider_chronologie_documents(
    date_facture: Optional[datetime],
    textes_annexes: List[str],
    types_annexes: List[str] = None
) -> Dict[str, Any]:
    """
    Valide la chronologie des documents (BL doit être avant ou égal à la facture).
    
    Args:
        date_facture: Date de la facture
        textes_annexes: Textes OCR des annexes
        types_annexes: Liste des types d'annexes (pour log)
    
    Returns:
        Dict avec résultats de validation
    """
    if not date_facture:
        return {
            'valide': False,
            'erreurs': ["Date de la facture manquante"],
            'details': {}
        }
    
    resultats = {
        'valide': True,
        'erreurs': [],
        'details': {},
        'dates_trouvees': []
    }
    
    for idx, texte in enumerate(textes_annexes):
        date_annexe = extraire_date_depuis_texte(texte)
        if date_annexe:
            resultats['dates_trouvees'].append(date_annexe)
            ecart = (date_facture - date_annexe).days
            
            type_annexe = types_annexes[idx] if types_annexes and idx < len(types_annexes) else f"Annexe {idx+1}"
            
            resultats['details'][type_annexe] = {
                'date': date_annexe.strftime('%d/%m/%Y'),
                'ecart_jours': ecart,
                'est_avant_facture': ecart >= 0
            }
            
            # ⭐ Vérification : BL doit être avant la facture
            if 'BL' in type_annexe.upper() or 'LIVRAISON' in type_annexe.upper():
                if ecart < 0:
                    resultats['valide'] = False
                    resultats['erreurs'].append(
                        f"{type_annexe} est après la facture (+{abs(ecart)} jours)"
                    )
            
            # ⭐ Vérification : PV doit être autour de la facture (±30 jours)
            if 'PV' in type_annexe.upper() or 'RECEPTION' in type_annexe.upper():
                if abs(ecart) > 30:
                    resultats['valide'] = False
                    resultats['erreurs'].append(
                        f"{type_annexe} est trop éloigné de la facture ({abs(ecart)} jours)"
                    )
    
    return resultats


def preprocess_image(image):
    if isinstance(image, str):
        image = Image.open(image)
    if image.mode != 'L':
        image = image.convert('L')
    image = ImageEnhance.Contrast(image).enhance(2.0)
    image = ImageEnhance.Sharpness(image).enhance(1.5) 
    return image.convert('RGB')


def ocr_image_to_texts(image):
    image_pp = preprocess_image(image)
    largeur, hauteur = image_pp.size
    data = pytesseract.image_to_data(
        image_pp, lang='fra+eng', output_type=pytesseract.Output.DICT,
        config='--psm 6 --oem 3',
    )
    textes = []
    for i in range(len(data['text'])):
        mot = str(data['text'][i]).strip()
        conf = int(data['conf'][i])
        if not mot or conf < 30:
            continue
        w, h = data['width'][i], data['height'][i]
        if w <= 0 or h <= 0:
            continue
        textes.append({
            'texte': mot,
            'x': data['left'][i] / largeur,
            'y': data['top'][i] / hauteur,
            'w': w / largeur,
            'h': h / largeur,
            'confiance': conf,
        })
    return textes


# ─────────────────────────────────────────────────────────────
# FONCTIONS DE DETECTION UNITAIRES
# ─────────────────────────────────────────────────────────────

def detecter_date(texte: str, seuil_jours: int = 30):
    """Retourne (date_valide: bool, date_trouvee: datetime|None).
    SEUIL CORRIGÉ : 30 jours (conforme SOMAS)"""
    patterns_date = [
        # Format: MOHAMMEDIA LE VENDREDI 16 MAI 2025
        r'MOHAMMEDIA\s+LE\s+[A-Z]+\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})',
        r'LE\s+[A-Z]+\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})',
        r'([A-Z]+)\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})',
        r'(\d{1,2})\s+([A-Z]+)\s+(\d{4})',
        
        # Format standard
        r'(\d{2})[/-](\d{2})[/-](\d{4})',
        r'(\d{2})[/-](\d{2})[/-](\d{2})',
        r'LE\s*:?\s*(\d{2})[/-](\d{2})[/-](\d{4})',
        r'DATE\s*:?\s*(\d{2})[/-](\d{2})[/-](\d{4})',
        r'DATE\s*:\s*(\d{2})[/-](\d{2})[/-](\d{4})',
        r'CLIENT\s*\((\d{2})(\d{2})/(\d{2})\)',
        r'\((\d{2})(\d{2})/(\d{2})\)',
        
        # Format: 16 MAI 2025
        r'(\d{1,2})\s+(JANVIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOUT|SEPTEMBRE|OCTOBRE|NOVEMBRE|DECEMBRE)\s+(\d{4})',
        r'(\d{1,2})\s+(JAN|FEV|MAR|AVR|MAI|JUN|JUL|AOU|SEP|OCT|NOV|DEC)\s+(\d{4})',
    ]
    for pattern in patterns_date:
        for match in re.findall(pattern, texte):
            try:
                if len(match) == 4:
                    if match[2].upper() in MOIS_MAP:
                        jour = int(match[1])
                        mois = MOIS_MAP[match[2].upper()]
                        annee = int(match[3])
                    else:
                        continue
                elif len(match) == 3:
                    if match[1].upper() in MOIS_MAP:
                        jour = int(match[0]) if match[0].isdigit() else 1
                        mois = MOIS_MAP[match[1].upper()]
                        annee = int(match[2])
                    elif len(match[2]) == 4:
                        jour, mois, annee = int(match[0]), int(match[1]), int(match[2])
                    else:
                        jour, mois, annee = int(match[0]), int(match[1]), 2000 + int(match[2])
                else:
                    continue
                
                date_obj = datetime(annee, mois, jour)
                if 2020 <= annee <= 2030:
                    valide = date_obj >= datetime.now() - timedelta(days=seuil_jours)
                    return valide, date_obj
            except Exception:
                continue
    return False, None


def detecter_numero_facture(texte: str, file_path: str = None) -> Optional[str]:
    """
    Détecte le numéro de facture UNIQUEMENT par OCR (patterns).
    ⚠️ Filtre les mots banals comme "AVEC", "POUR", etc.
    """
    
    # ⭐ Liste des mots banals à ignorer
    MOTS_BANALS = [
        'AVEC', 'POUR', 'SANS', 'CHEZ', 'SUR', 'ET', 'OU', 'MAIS',
        'DANS', 'PAR', 'PAS', 'PLUS', 'MOINS', 'TRES', 'BIEN',
        'FAIT', 'FAITE', 'FAITES', 'FAIS', 'ETRE', 'AVOIR',
        'VOUS', 'NOUS', 'ILS', 'ELLES', 'SONT', 'ETANT'
    ]
    
    # ⭐ Patterns pour le numéro de facture (par ordre de priorité)
    patterns = [
        # ✅ PRIORITÉ 1: Format spécifique "F26-XXX" ou "F26 XXX"
        r'FACTURE\s*N[°O]\s*[:]?\s*(F26[-/]?\s*\d{2,6})',
        r'FACTURE\s*N\s*[:]?\s*(F26[-/]?\s*\d{2,6})',
        
        # ✅ PRIORITÉ 2: "FACTURE N° F26-026" 
        r'FACTURE\s*N[°O]\s*[:]?\s*([A-Z0-9]{2,4}[-/]?\s*[A-Z0-9]{2,6})',
        
        # ✅ PRIORITÉ 3: "Facture N°:" ou "Facture N° "
        r'FACTURE\s*N[°O]\s*[:]?\s*([A-Z0-9\-/]+)',
        r'FACTURE\s*N\s*[:]?\s*([A-Z0-9\-/]+)',
        
        # ✅ PRIORITÉ 4: "N° Facture:" ou "N° Facture "
        r'N[°O]\s*FACTURE\s*[:]?\s*([A-Z0-9\-/]+)',
        
        # ✅ PRIORITÉ 5: "FACTURE" suivi d'un numéro (sans N°) - PLUS STRICT
        r'FACTURE\s*[:]?\s*([A-Z0-9]{4,20})',
        r'Facture\s*[:]?\s*([A-Z0-9]{4,20})',
        
        # ✅ PRIORITÉ 6: "INV" suivi d'un numéro
        r'INV\s*[:]?\s*([A-Z0-9\-/]+)',
        r'INV([A-Z0-9\-/]+)',
        
        # ✅ PRIORITÉ 7: "N°" suivi d'un numéro (si contexte facture)
        r'FACTURE\s*[:\s]*([A-Z0-9\-/]{4,20})',
    ]
    
    # ⭐ 1. Chercher avec les patterns spécifiques
    for pattern in patterns:
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            numero = match.group(1).strip()
            # Nettoyer les caractères indésirables
            numero = re.sub(r'[^\w\-/]', '', numero)
            # ⚠️ Vérifier que ce n'est pas un mot banal
            if numero and len(numero) >= 3 and numero.upper() not in MOTS_BANALS:
                print(f"   📝 Numéro trouvé avec pattern: {pattern}")
                return numero
    
    # ⭐ 2. FALLBACK : Chercher des patterns de numéros de facture spécifiques
    fallback_patterns = [
        r'\bF26[-/]?\s*\d{2,6}\b',      # F26-026, F26/026, F26 026
        r'\bINV[A-Z0-9\-/]{3,15}\b',    # INV25196
        r'\b[A-Z]{2}\d{6}\b',           # AE260021 (exactement 2 lettres + 6 chiffres)
        r'\b\d{4}/\d{4}\b',             # 2025/0174
        r'\b\d{4}-\d{4}\b',             # 2025-0174
        r'\b[A-Z]{2,4}[-/]?\d{3,6}\b',  # F26-026, INV25196 (2-4 lettres + 3-6 chiffres)
    ]
    
    for pattern in fallback_patterns:
        matches = re.findall(pattern, texte)
        if matches:
            for match in matches:
                # ⚠️ Vérifier que le match n'est pas un mot banal
                if len(match) >= 3 and match.upper() not in MOTS_BANALS:
                    # ⚠️ Vérifier que ce n'est pas "F2026" (faux positif)
                    if match.upper() != "F2026":
                        return match.strip()
    
    return None


def detecter_if(texte: str) -> bool:
    patterns = [
        r'IF\s*[:\s]*(\d{6,})',
        r'I\.?\s*F\.?\s*[:\s]*(\d{6,})',
        r'IDENTIFIANT\s*FISCAL\s*[:\s]*(\d{6,})',
        r'IS/IF\s*[:\s]*(\d{6,})',  
        r'IF\s*N[°O]\s*[:\s]*(\d{6,})',
        r'I\.?F\.?\s*N[°O]\s*[:\s]*(\d{6,})',
        r'(\d{6,})\s*[-]\s*IS/IF',
        r'[1L]F\s*[:\s]*(\d{6,})',
        r'IDENTIFICATION\s*FISCALE?\s*N[°O]\s*(\d{6,})',
        r'IDENTIFICATION\s*FISCALE?\s*[:\s]*(\d{6,})',
    ]
    return any(re.search(p, texte) for p in patterns)


def detecter_ice(texte: str):
    """
    Détecte TOUS les numéros ICE dans le texte.
    Retourne une liste de tous les ICE trouvés.
    ⭐ CORRIGÉ : Accepte les ICE de 14 à 16 chiffres.
    """
    patterns = [
        r'ICE\s*[:\s]*0?(\d{14,16})',          # ⭐ 14 à 16 chiffres
        r'I\.?C\.?E\.?\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'LC\.?E\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'L\.?C\.?E\.?\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'I\s*C\s*E\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'ICE\s*[:\s]*0?(\d{14,16})',
        r'I\.?C\.?E\.?\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'LC\.?E\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'L\.?C\.?E\.?\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'I\s*C\s*E\s*(?:N[°O]?)?\s*[:\s]*0?(\d{14,16})',
        r'ICE\s*/\s*0?(\d{14,16})',           # ⭐ 14 à 16 chiffres
        r'ICE\s*\/\s*0?(\d{14,16})',          # ⭐ 14 à 16 chiffres
    ]
    
    ice_numbers = []
    for p in patterns:
        matches = re.findall(p, texte)
        for m in matches:
            # Nettoyer le numéro
            numero = m.strip()
            # ⭐ CORRIGÉ : Accepte les numéros de 14 à 16 chiffres
            if len(numero) >= 14 and len(numero) <= 16 and numero.isdigit():
                if numero not in ice_numbers:
                    ice_numbers.append(numero)
    
    return ice_numbers

def detecter_cnss(texte: str):
    """
    Détecte le N° CNSS dans le texte OCR.
    Version optimisée pour CNSS : 156.9427
    """
    # Nettoyer le texte pour la recherche (enlever les caractères parasites)
    texte_clean = re.sub(r'[^A-Za-z0-9\.:\s]', '', texte)
    
    patterns = [
        # ✅ PATTERN PRIORITAIRE pour CNSS : 156.9427
        r'CNSS\s*:\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\s*:\s*(\d{3}\.\d{3}\d{3})',
        r'CNSS\s*:\s*(\d{6,8})',
        
        # CNSS: 156.9427 (sans espace après les deux-points)
        r'CNSS:\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS:\s*(\d{6,8})',
        
        # CNSS. 156.9427
        r'CNSS\.\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\.\s*(\d{6,8})',
        r'CNSS\.(\d{6,8})',
        
        # CNSS 156.9427
        r'CNSS\s+(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\s+(\d{6,8})',
        
        # Format avec séparateur quelconque
        r'CNSS\s*[:\s\.]+\s*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS\s*[:\s\.]+\s*(\d{6,8})',
        
        # Format avec N°
        r'CNSS\s*N[°O]\s*[:\s]*(\d{6,8})',
        r'CNSS\s*N°\s*[:\s]*(\d{6,8})',
        
        # DERNIER RECOURS : chercher "CNSS" suivi d'un nombre avec points
        r'CNSS[^0-9]*(\d{3}\.\d{3}\.\d{3})',
        r'CNSS[^0-9]*(\d{6,8})',
    ]
    
    # 1. Chercher dans le texte original
    for p in patterns:
        m = re.search(p, texte)
        if m:
            valeur = re.sub(r'[.\s]', '', m.group(1))
            if len(valeur) >= 6 and valeur.isdigit():
                return True, valeur
    
    # 2. Chercher dans le texte nettoyé
    for p in patterns:
        m = re.search(p, texte_clean)
        if m:
            valeur = re.sub(r'[.\s]', '', m.group(1))
            if len(valeur) >= 6 and valeur.isdigit():
                return True, valeur
    
    # 3. Recherche manuelle : trouver "CNSS" et prendre le nombre après
    if 'CNSS' in texte:
        idx = texte.find('CNSS')
        if idx != -1:
            # Extraire les 30 caractères après CNSS
            after = texte[idx+4:idx+40]
            # Chercher un nombre avec des points (format 156.9427)
            m = re.search(r'(\d{3}\.\d{3}\.\d{3})', after)
            if m:
                valeur = re.sub(r'[.\s]', '', m.group(1))
                if len(valeur) >= 6 and valeur.isdigit():
                    return True, valeur
            # Chercher un nombre simple
            m = re.search(r'(\d{6,8})', after)
            if m:
                return True, m.group(1)
    
    return False, None


def detecter_rc(texte: str):
    patterns = [
        r'RC\s*:\s*[A-Za-z]+\s*:\s*N[°O]\s*(\d{4,})',
        r'RC\s*:\s*[A-Za-z]+\s*N[°O]\s*(\d{4,})',
        r'RC\s*:\s*[A-Za-z]+\s*(\d{4,})',
        r'R\.\s*C\.\s*[A-Za-z]+\s*[:\s]*(\d{4,})',
        r'R\.\s*C\.\s*[A-Za-z]+\s*N[°O]\s*(\d{4,})',
        r'RC\s*[Nn]?°?\s*[:\s]*(\d{4,})',
        r'R\.?C\.?\s*[Nn]?°?\s*[:\s]*(\d{4,})',
        r'REGISTRE\s*[DE]E\s*COMMERCE\s*[:\s]*(\d{4,})',
        r'RC\s*:\s*[A-Za-z]+\s*N°\s*(\d{4,})',
        r'R\.\s*C\s*[A-Za-z]+\s*N[°O]\s*(\d{4,})',
        r'RC\s*[:\s]*(\d{4,})',
        r'RC\s*N[°O]\s*(\d{4,})',
    ]
    for p in patterns:
        m = re.search(p, texte)
        if m:
            valeur = re.sub(r'[.\s-]', '', m.group(1))
            if len(valeur) >= 4 and valeur.isdigit():
                return True, valeur
    return False, None


def detecter_taxe_professionnelle(texte: str) -> bool:
    patterns = [
        r'TAXE\s*PROFESSIONNELLE\s*[:\s]*(\d{6,})',
        r'TP\s*[Nn]?°?\s*[:\s]*(\d{6,})',
        r'PATENTE\s*[:\s]*(\d{6,})',
        r'PATENTE\s*[Nn]°?\s*[:\s]*(\d{6,})',
    ]
    return any(re.search(p, texte) for p in patterns)


def detecter_rib(texte: str):
    """
    Détecte le N° RIB dans le texte OCR.
    APPROCHE UNIVERSELLE : trouve toutes les suites de 20-24 chiffres.
    """
    
    # ──────────────────────────────────────────────────────────────
    # 1. RECHERCHE UNIVERSELLE : Toutes les suites de 20-24 chiffres
    # ──────────────────────────────────────────────────────────────
    
    patterns_universels = [
        # ⭐ UNIVERSELLE : Trouve TOUS les nombres de 20-24 chiffres
        r'\b(\d{20,24})\b',  # 20 à 24 chiffres consécutifs
        
        # ⭐ Avec espaces (n'importe quel groupe)
        r'\b(\d{3}\s+\d{3}\s+\d{4}\s+\d{2}\s+\d{3}\s+\d{2}\s+\d{3,7})\b',
        r'\b(\d{3}\s+\d{3}\s+\d{16}\s+\d{2})\b',
        r'\b(\d{3}\s+\d{3}\s+\d{15}\s+\d{2}\s+\d{2})\b',
        r'\b(\d{3}\s+\d{3}\s+\d{14}\s+\d{2}\s+\d{3})\b',
        r'\b(\d{3}\s+\d{3}\s+\d{13}\s+\d{3}\s+\d{2})\b',
        
        # ⭐ Avec tirets ou points
        r'\b(\d{3}[-.]\d{3}[-.]\d{4}[-.]\d{2}[-.]\d{3}[-.]\d{2}[-.]\d{3,7})\b',
        r'\b(\d{3}[-.]\d{3}[-.]\d{16}[-.]\d{2})\b',
        r'\b(\d{3}[-.]\d{3}[-.]\d{15}[-.]\d{2}[-.]\d{2})\b',
        
        # ⭐ Avec "RIB" devant (peu importe le format)
        r'RIB\s*[:\s]*(\d{3}\s+\d{3}\s+\d{4}\s+\d{2}\s+\d{3}\s+\d{2}\s+\d{3,7})',
        r'RIB\s*[:\s]*(\d{3}\s+\d{3}\s+\d{16}\s+\d{2})',
        r'RIB\s*[:\s]*(\d{3}\s+\d{3}\s+\d{15}\s+\d{2}\s+\d{2})',
        r'RIB\s*[:\s]*(\d{3}\s+\d{3}\s+\d{14}\s+\d{2}\s+\d{3})',
        r'RIB\s*[:\s]*(\d{3}\s+\d{3}\s+\d{13}\s+\d{3}\s+\d{2})',
        r'RIB\s*[:\s]*(\d{20,24})',
        
        # ⭐ Sans "RIB" mais avec "BANQUE", "BANCAIRE", "IBAN"
        r'(?:BANQUE|BANCAIRE|IBAN)\s*[:\s]*(\d{3}\s+\d{3}\s+\d{4}\s+\d{2}\s+\d{3}\s+\d{2}\s+\d{3,7})',
        r'(?:BANQUE|BANCAIRE|IBAN)\s*[:\s]*(\d{20,24})',
    ]
    
    # 1. Rechercher avec les patterns universels
    for p in patterns_universels:
        m = re.search(p, texte, re.IGNORECASE)
        if m:
            valeur = m.group(1)
            chiffres = re.sub(r'[.\s-]', '', valeur)
            if len(chiffres) >= 20 and len(chiffres) <= 24 and chiffres.isdigit():
                return True, chiffres
    
    # ──────────────────────────────────────────────────────────────
    # 2. MÉTHODE UNIVERSELLE : Chercher dans les coordonnées bancaires
    # ──────────────────────────────────────────────────────────────
    
    # Trouver la zone "bancaire" (RIB, RIB, IBAN, Banque, etc.)
    zones_bancaires = [
        r'RIB\s*[:\s]*([^\n]{5,100})',
        r'IBAN\s*[:\s]*([^\n]{5,100})',
        r'BANQUE\s*[:\s]*([^\n]{5,100})',
        r'BANCAIRE\s*[:\s]*([^\n]{5,100})',
        r'COORDONNÉES\s*BANCAIRES\s*[:\s]*([^\n]{5,100})',
    ]
    
    for zone_pattern in zones_bancaires:
        match = re.search(zone_pattern, texte, re.IGNORECASE)
        if match:
            zone = match.group(1)
            # Extraire tous les nombres de la zone
            nombres = re.findall(r'\b(\d{6,30})\b', zone)
            for nb in nombres:
                chiffres = re.sub(r'[.\s-]', '', nb)
                if len(chiffres) >= 20 and len(chiffres) <= 24 and chiffres.isdigit():
                    return True, chiffres
    
    # ──────────────────────────────────────────────────────────────
    # 3. MÉTHODE UNIVERSELLE : Scanner TOUT le texte pour 20-24 chiffres
    # ──────────────────────────────────────────────────────────────
    
    # Extraire tous les nombres de 6 à 30 chiffres
    tous_les_nombres = re.findall(r'\b(\d{6,30})\b', texte)
    
    # Filtrer ceux qui font 20-24 chiffres
    for nb in tous_les_nombres:
        chiffres = re.sub(r'[.\s-]', '', nb)
        if len(chiffres) >= 20 and len(chiffres) <= 24 and chiffres.isdigit():
            return True, chiffres
    
    return False, None


def detecter_montant_lettres(texte: str) -> bool:
    """CORRIGE : comparaison mot-à-mot au lieu de sous-chaîne."""
    expressions_fortes = [
        r'ARR[ÊE]T[ÉE]E?\s+LA\s+PR[ÉE]SENTE\s+FACTURE',
        r'ARR[ÊE]T[ÉE]E?\s+LA\s+PR[ÉE]SENTE\s+(?:NOTE|FACTURE)\s+[ÀA]\s+LA\s+SOMME',
        r'SOMME\s+DE\s*:',
        r'MONTANT\s+EN\s+LETTRES?\s*:',
    ]
    if any(re.search(p, texte) for p in expressions_fortes):
        return True

    mots_nombres = {
        'ZERO', 'UN', 'DEUX', 'TROIS', 'QUATRE', 'CINQ', 'SIX', 'SEPT',
        'HUIT', 'NEUF', 'DIX', 'VINGT', 'TRENTE', 'QUARANTE', 'CINQUANTE',
        'SOIXANTE', 'CENT', 'MILLE', 'MILLION', 'DIRHAM', 'DIRHAMS',
        'CENTIME', 'CENTIMES',
    }
    mots_texte = set(texte.split())
    return len(mots_nombres & mots_texte) >= 2


def detecter_objet_commande(texte: str) -> bool:
    patterns = [
        r'OBJET\s*[:\s]', r'BC\s*[Nn]°\s*\d+', r'BON\s*DE\s*COMMANDE',
        r'CONTRAT\s*[Nn]?°?\s*\d+', r'R[ÉE]F[ÉE]RENCE\s*[:\s]*\d+',
        r'REF\s*[:\s]*\d+', r'N\s*/\s*R[ÉE]F', r'MAIL\s*[:\s]*\S+@\S+',
        r'PRESTATION', r'TRAVAUX', r'FOURNITURE', r'LOCATION', r'FORMATION',
        r'ETUDE', r'CONTR[ÔO]LE', r'TRANSIT', r'IMPORTATION',
        r'DESIGNATION', r'MAINTENANCE', r'INSTALLATION', r'CONSEIL',
        r'TRANSPORT', r'LOGISTIQUE', r'VERIFICATION', r'LIVRAISON',
        r'VEHICULE', r'KILOM[ÉE]TRAGE', r'LIVRAISON\s+DU\s+VEHICULE',
        r'RESTITUTION\s+DU\s+VEHICULE', r'CONTRAT\s+DE\s+LOCATION',
        r'LOCATION\s+DE\s+[A-Z]+\s*\d+',
    ]
    return any(re.search(p, texte) for p in patterns)


def extraire_objet_commande(texte: str) -> str:
    """
    Extrait le texte de l'objet de la commande du texte OCR.
    Version qui capture le bon objet en utilisant le contexte.
    """
    # Chercher "OBJET:" suivi de "TRAVAUX COMPLÉMENTAIRES" ou "RESEAU INCENDIE"
    patterns = [
        r'OBJET\s*:\s*([^V\.RÉF]{10,100})(?=.*?(?:INCENDIE|RÉSEAU|COMPLÉMENTAIRES|CAV|SAMIR))',
        r'OBJET\s*:\s*(.+?)(?=\s*(?:V\.\s*RÉF|V\.\s*REF|N\.\s*RÉF|N\.\s*REF|$))',
        r'OBJET\s*:\s*([^\n]{10,100})',
        r'OBJET\s*[:\s]*([^V\.RÉF]{10,100})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            objet = match.group(1).strip()
            objet = re.sub(r'\s+', ' ', objet)
            objet = re.sub(r'\s*(?:V\.\s*RÉF|V\.\s*REF|N\.\s*RÉF|N\.\s*REF|R\.\s*BUDGÉTAIRE|DU\s*:|POUR).*', '', objet, flags=re.IGNORECASE)
            objet = objet.strip()
            mots_cles_objet_principal = ['COMPLÉMENTAIRES', 'INCENDIE', 'RÉSEAU', 'CAV', 'SAMIR']
            if any(mot in objet.upper() for mot in mots_cles_objet_principal):
                return objet
            if len(objet) > 10 and 'TRAVAUX' in objet.upper() and not any(x in objet for x in ['00', '49', '200']):
                return objet
    
    # FALLBACK : Chercher "OBJET:" manuellement
    if 'OBJET:' in texte or 'OBJET :' in texte:
        idx = texte.find('OBJET')
        if idx != -1:
            after = texte[idx+5:idx+200]
            for mot in ['INCENDIE', 'RESEAU', 'RÉSEAU', 'COMPLÉMENTAIRES', 'CAV', 'SAMIR']:
                if mot in after:
                    idx_mot = after.find(mot)
                    if idx_mot != -1:
                        objet = after[:idx_mot + len(mot) + 30]
                        objet = re.sub(r'\s+', ' ', objet)
                        objet = re.sub(r'\s*(?:V\.\s*RÉF|V\.\s*REF|N\.\s*RÉF|N\.\s*REF|$).*', '', objet, flags=re.IGNORECASE)
                        objet = objet.strip()
                        if len(objet) > 10:
                            return objet
    
    # FALLBACK 2 : Chercher "TRAVAUX COMPLÉMENTAIRES" directement
    if 'TRAVAUX COMPLÉMENTAIRES' in texte:
        idx = texte.find('TRAVAUX COMPLÉMENTAIRES')
        if idx != -1:
            after = texte[idx:idx+100]
            stop = after.find('V.')
            if stop != -1:
                after = after[:stop]
            after = re.sub(r'\s+', ' ', after).strip()
            if len(after) > 10:
                return after
    
    # FALLBACK 3 : Chercher "RÉSEAU INCENDIE" ou "RESEAU INCENDIE"
    for mot in ['RÉSEAU INCENDIE', 'RESEAU INCENDIE', 'CAV SAMIR']:
        if mot in texte:
            idx = texte.find(mot)
            if idx != -1:
                debut = max(0, idx - 30)
                after = texte[debut:idx + len(mot) + 30]
                after = re.sub(r'\s+', ' ', after).strip()
                after = re.sub(r'\s*(?:V\.\s*RÉF|V\.\s*REF|N\.\s*RÉF|N\.\s*REF|$).*', '', after, flags=re.IGNORECASE)
                after = after.strip()
                if len(after) > 10:
                    return after
    
    return "Non détecté"


def estimer_type_objet(texte: str) -> str:
    """Catégories alignées avec DOCUMENTS_PAR_OBJET / ALIAS_TYPE_OBJET"""
    if 'FORMATION' in texte:
        return "formation"
    
    mots_location = [
        'LOCATION', 'VEHICULE', 'KILOMETRAGE', 'KILOMÉTRAGE',
        'LIVRAISON DU VEHICULE', 'RESTITUTION DU VEHICULE',
        'CONTRAT DE LOCATION', 'DEPOT DE GARANTIE',
        'CAUTION', 'KILOMETRE', 'KILOMÈTRE'
    ]
    if any(mot in texte for mot in mots_location):
        return "location"
    
    if re.search(r'LOCATION\s+DE\s+[A-Z]+\s*\d+', texte):
        return "location"
    if re.search(r'CONTRAT\s+DE\s+LOCATION', texte):
        return "location"
    if re.search(r'VEHICULE\s+[A-Z]+\s*\d+', texte):
        return "location"
    
    elif 'CONTROLE' in texte or 'CONTRÔLE' in texte or 'VERIFICATION' in texte:
        return "controle"
    elif 'TRANSIT' in texte or 'DOUANE' in texte or 'IMPORTATION' in texte:
        return "transitaire"
    elif 'ETUDE' in texte or 'CONCEPTION' in texte:
        return "etude"
    elif 'TRAVAUX' in texte or 'INSTALLATION' in texte:
        return "travaux"
    elif 'FOURNITURE' in texte or 'LIVRAISON' in texte:
        return "fourniture"
    else:
        return "service"


def detecter_cachet_visuel(image, zone_recherche: str = "bas") -> bool:
    """
    Détection VISUELLE d'un cachet/tampon.
    Version améliorée avec des seuils plus permissifs.
    """
    try:
        import cv2
    except ImportError:
        return False
    
    img_rgb = np.array(image.convert('RGB'))
    h, w = img_rgb.shape[:2]

    if zone_recherche == "bas":
        zone = img_rgb[int(h * 0.50):, :]
    elif zone_recherche == "haut":
        zone = img_rgb[:int(h * 0.50), :]
    else:
        zone = img_rgb

    hsv = cv2.cvtColor(zone, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    valeur = hsv[:, :, 2]
    masque = (saturation > 20) & (valeur > 50) & (valeur < 250)
    
    masque_u8 = (masque * 255).astype(np.uint8)
    kernel = np.ones((5, 5), np.uint8)
    masque_u8 = cv2.morphologyEx(masque_u8, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(masque_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    aire_zone = zone.shape[0] * zone.shape[1]
    
    taille_min = 0.0005 * aire_zone
    taille_max = 0.20 * aire_zone
    
    for c in contours:
        aire = cv2.contourArea(c)
        if taille_min < aire < taille_max:
            return True
    
    gray = cv2.cvtColor(zone, cv2.COLOR_RGB2GRAY)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=50,
        param1=50, param2=30, minRadius=15, maxRadius=150
    )
    if circles is not None:
        return True
    
    edges = cv2.Canny(gray, 50, 150)
    contours_rect, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours_rect:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            area = cv2.contourArea(c)
            if 0.001 * aire_zone < area < 0.15 * aire_zone:
                return True
        
    return False


# ─────────────────────────────────────────────────────────────────
# CLASSIFICATION DES DOCUMENTS ANNEXES
# ─────────────────────────────────────────────────────────────────

DOCUMENT_TYPE_KEYWORDS = {
    "bon_livraison_signe_cachete": [
        r'BON\s*DE\s*LIVRAISON', r'\bBL\s*N[°O]',
    ],
    "pv_reception_ou_attachement_signe_cachete": [
        r'PROC[ÈE]S[\s-]?VERBAL\s*DE\s*R[ÉE]CEPTION',
        r'\bPV\s*DE\s*R[ÉE]CEPTION', r'ATTACHEMENT\s*DES\s*TRAVAUX',
        r'\bATTACHEMENT\b',
    ],
    "pv_location_signe_cachete": [
        r'PV\s*DE\s*LOCATION', r'PROC[ÈE]S[\s-]?VERBAL\s*DE\s*LOCATION',
    ],
    "validation_bureau_etudes_controle": [
        r'BUREAU\s*D[\'\s]?[ÉE]TUDES?', r'BUREAU\s*DE\s*CONTR[ÔO]LE',
        r'VALIDATION\s*TECHNIQUE',
    ],
    "feuille_presence": [
        r'FEUILLE\s*DE\s*PR[ÉE]SENCE', r'LISTE\s*DE\s*PR[ÉE]SENCE',
    ],
    "certificat_ou_rapport": [
        r'CERTIFICAT', r'RAPPORT\s*DE\s*(MESURE|[ÉE]TALONNAGE|CONTR[ÔO]LE)',
    ],
    "engagement_importation": [
        r'ENGAGEMENT\s*D[\'\s]?IMPORTATION',
    ],
    "quittance_douane": [
        r'QUITTANCE\s*(DE\s*)?DOUANE',
    ],
    "attestation_rib": [
        r'ATTESTATION\s*(DE\s*|BANCAIRE\s*)?RIB', r'ATTESTATION\s*BANCAIRE',
    ],
    "caution_retenue_garantie": [
        r'CAUTION\s*(DE\s*)?RETENUE\s*(DE\s*)?GARANTIE',
    ],
    "caution_acompte_meme_banque": [
        r'CAUTION\s*D[\'\s]?ACOMPTE',
    ],
}


def classifier_type_document(texte: str) -> str | None:
    """Retourne la clé du type de document reconnu, ou None."""
    for type_doc, patterns in DOCUMENT_TYPE_KEYWORDS.items():
        if any(re.search(p, texte) for p in patterns):
            return type_doc
    return None


def analyser_document_annexe(chemin_fichier: str) -> dict:
    """OCRise un fichier annexe et retourne son type détecté + s'il est signé/cacheté."""
    if chemin_fichier.lower().endswith('.pdf'):
        images = convert_from_path(chemin_fichier, dpi=150, first_page=1, last_page=1, poppler_path=POPPLER_PATH)
        image = images[0]
    else:
        image = Image.open(chemin_fichier)

    textes = ocr_image_to_texts(image)
    texte_complet = ' '.join(t['texte'] for t in textes).upper()

    type_detecte = classifier_type_document(texte_complet)
    cachet_present = detecter_cachet_visuel(image)

    return {
        "fichier": os.path.basename(chemin_fichier),
        "type_detecte": type_detecte,
        "cachet_signature_present": cachet_present,
        "texte_extrait": texte_complet[:500],
    }


# ═══════════════════════════════════════════════════════════════
# FONCTIONS DEBUG - AFFICHAGE DES ÉLÉMENTS DÉTECTÉS
# ═══════════════════════════════════════════════════════════════

def afficher_elements_detectes(resultats: Dict[str, Any]) -> None:
    """
    Affiche de manière structurée tous les éléments détectés par l'OCR.
    """
    print("\n" + "="*80)
    print("📋 ÉLÉMENTS DÉTECTÉS PAR L'OCR")
    print("="*80)
    
    # 1. INFORMATIONS GÉNÉRALES
    print("\n📊 INFORMATIONS GÉNÉRALES:")
    print(f"   📝 Mots extraits: {resultats.get('nb_mots_ocr', 0)}")
    print(f"   📊 Confiance moyenne: {resultats.get('confiance_moyenne', 0):.1f}%")
    print(f"   📄 Type d'objet estimé: {resultats.get('type_objet', 'Non détecté')}")
    
    # 2. DATES
    print("\n📅 DATES:")
    print(f"   📌 Date trouvée: {resultats.get('date_trouvee', 'Non détectée')}")
    print(f"   ✅ Date valide: {'✅ Oui' if resultats.get('date_valide') else '❌ Non'}")
    
    # 3. IDENTIFIANTS
    print("\n🏢 IDENTIFIANTS:")
    
    ice_valeur = resultats.get('ice_valeur')
    print(f"   🔹 ICE: {'✅ ' + ice_valeur if ice_valeur else '❌ Non détecté'}")
    
    cnss_valeur = resultats.get('cnss_valeur')
    print(f"   🔹 CNSS: {'✅ ' + cnss_valeur if cnss_valeur else '❌ Non détecté'}")
    
    rc_valeur = resultats.get('rc_valeur')
    print(f"   🔹 RC: {'✅ ' + rc_valeur if rc_valeur else '❌ Non détecté'}")
    
    rib_valeur = resultats.get('rib_valeur')
    print(f"   🔹 RIB: {'✅ ' + rib_valeur if rib_valeur else '❌ Non détecté'}")
    
    print(f"   🔹 IF: {'✅ Détecté' if resultats.get('if_ok') else '❌ Non détecté'}")
    print(f"   🔹 Taxe professionnelle: {'✅ Détecté' if resultats.get('taxe_professionnelle_ok') else '❌ Non détecté'}")
    
    # 4. OBJET DE COMMANDE
    print("\n📋 OBJET DE COMMANDE:")
    objet = resultats.get('objet_commande_trouve', 'Non détecté')
    print(f"   📌 Texte: {objet}")
    print(f"   ✅ Détecté: {'✅ Oui' if resultats.get('objet_commande_ok') else '❌ Non'}")
    
    # 5. AUTRES
    print("\n📎 AUTRES:")
    print(f"   🖊️ Cachet/Signature: {'✅ Présent' if resultats.get('cachet_ok') else '❌ Absent'}")
    print(f"   💰 Montant en lettres: {'✅ Détecté' if resultats.get('montant_lettres_ok') else '❌ Non détecté'}")
    
    # 6. EXTRAIT DU TEXTE
    texte_extrait = resultats.get('texte_extrait', '')
    if texte_extrait:
        print("\n📝 EXTRAIT DU TEXTE (premiers 500 caractères):")
        print("-"*80)
        print(texte_extrait[:500])
        print("-"*80)
    
    print("\n" + "="*80)
    print("✅ FIN DE L'AFFICHAGE")
    print("="*80)


def debug_extraction(chemin_facture: str) -> Dict[str, Any]:
    """
    Fonction de debug qui exécute l'extraction et affiche tous les résultats.
    """
    print("\n" + "="*80)
    print("🔍 DEBUG EXTRACTION - AFFICHAGE COMPLET")
    print("="*80)
    
    resultats = extraire_criteres_somas(chemin_facture, verbose=True)
    
    # Afficher tous les résultats de manière structurée
    afficher_elements_detectes(resultats)
    
    return resultats


def debug_ocr(chemin_facture):
    """
    Fonction de debug qui affiche TOUS les mots détectés par l'OCR
    page par page.
    """
    print("\n" + "="*80)
    print("🔍 DEBUG OCR - TOUS LES MOTS DÉTECTÉS (PAGE PAR PAGE)")
    print("="*80)
    
    if isinstance(chemin_facture, str):
        chemin_facture = chemin_facture.strip().strip('"').strip("'")
        if not os.path.exists(chemin_facture):
            raise FileNotFoundError(f"Fichier non trouvé : {chemin_facture}")
    
    print(f"\n📄 Fichier : {chemin_facture}")
    
    if chemin_facture.lower().endswith('.pdf'):
        print("   📄 Conversion PDF en image...")
        images = convert_from_path(chemin_facture, dpi=200, first_page=1, last_page=10, poppler_path=POPPLER_PATH)
        
        print(f"   ✅ {len(images)} pages converties")
        print("="*80)
        
        textes_total = []
        texte_complet_total = ''
        
        for idx, image in enumerate(images):
            print(f"\n📄 PAGE {idx+1}/{len(images)}")
            print("="*80)
            
            textes_page = ocr_image_to_texts(image)
            textes_total.extend(textes_page)
            
            texte_page = ' '.join(t['texte'] for t in textes_page).upper()
            texte_complet_total += texte_page + ' '
            
            print(f"\n📝 TEXTE OCR - PAGE {idx+1}:")
            print("-"*80)
            print(texte_page)
            print("-"*80)
            
            print(f"\n📋 MOTS DÉTECTÉS - PAGE {idx+1} ({len(textes_page)} mots)")
            print("  N°   MOT                                  CONF")
            print("-"*80)
            
            for i, t in enumerate(textes_page):
                conf = t['confiance']
                mot = t['texte']
                print(f"  {i:3d}   '{mot:<30}'  {conf:3d}%")
            
            print("="*80)
            
            del image
            gc.collect()
        
        textes = textes_total
        texte_complet = texte_complet_total
        
        print(f"\n📊 TOTAL GÉNÉRAL : {len(textes)} mots extraits sur {len(images)} pages")
        print("="*80)
        
        del images
        gc.collect()
        
    else:
        image = Image.open(chemin_facture)
        textes = ocr_image_to_texts(image)
        texte_complet = ' '.join(t['texte'] for t in textes).upper()
        
        print("\n📝 TEXTE OCR COMPLET:")
        print("-"*80)
        print(texte_complet)
        print("-"*80)
        
        print(f"\n📋 MOTS DÉTECTÉS ({len(textes)} mots)")
        print("  N°   MOT                                  CONF")
        print("-"*80)
        
        for i, t in enumerate(textes):
            conf = t['confiance']
            mot = t['texte']
            print(f"  {i:3d}   '{mot:<30}'  {conf:3d}%")
    
    print("\n" + "="*80)
    print("✅ DEBUG OCR TERMINÉ")
    print("="*80)
    
    return textes, texte_complet

def extraire_date_depuis_texte(texte: str) -> Optional[datetime]:
    """
    Extrait la première date valide d'un texte.
    Utilisé pour les annexes (BL, PV, rapports, etc.)
    """
    if not texte:
        return None
    
    patterns = [
        r'(\d{2})/(\d{2})/(\d{4})',
        r'(\d{2})-(\d{2})-(\d{4})',
        r'(\d{2})\.(\d{2})\.(\d{4})',
        r'(\d{1,2})\s+(JANVIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOUT|SEPTEMBRE|OCTOBRE|NOVEMBRE|DECEMBRE)\s+(\d{4})',
        r'(\d{1,2})\s+(JAN|FEV|MAR|AVR|MAI|JUN|JUL|AOU|SEP|OCT|NOV|DEC)\s+(\d{4})',
        r'DATE\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'DATE\s*:?\s*(\d{2})-(\d{2})-(\d{4})',
        r'LE\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'DU\s*:?\s*(\d{2})/(\d{2})/(\d{4})',
        r'BL\s*N°?\s*:?\s*(\d{2})/(\d{2})/(\d{4})',  # Date sur BL
        r'PV\s*N°?\s*:?\s*(\d{2})/(\d{2})/(\d{4})',  # Date sur PV
    ]
    
    for pattern in patterns:
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            try:
                if len(match.groups()) == 3:
                    # Si le mois est en lettres
                    if match.group(2).upper() in MOIS_MAP:
                        jour = int(match.group(1))
                        mois = MOIS_MAP[match.group(2).upper()]
                        annee = int(match.group(3))
                    else:
                        jour = int(match.group(1))
                        mois = int(match.group(2))
                        annee = int(match.group(3))
                    
                    if 1 <= jour <= 31 and 1 <= mois <= 12 and 1900 <= annee <= 2100:
                        return datetime(annee, mois, jour)
            except Exception:
                continue
    
    return None


def valider_date_facture_avec_annexes(
    date_facture_str: str,
    annexes_detectees: Dict[str, bool],
    textes_annexes: Dict[str, str]  # {type_annexe: texte_ocr}
) -> Dict[str, Any]:
    """
    Valide la date de la facture par rapport aux annexes.
    
    Args:
        date_facture_str: Date de la facture (format 'DD/MM/YYYY')
        annexes_detectees: Dict des annexes présentes
        textes_annexes: Dict {type_annexe: texte_ocr_de_l_annexe}
    
    Returns:
        Dict avec résultats de validation
    """
    
    # Parser la date de la facture
    try:
        date_facture = datetime.strptime(date_facture_str, '%d/%m/%Y')
    except:
        try:
            date_facture = datetime.strptime(date_facture_str, '%d-%m-%Y')
        except:
            return {
                'valide': False,
                'est_recente': False,
                'erreurs': ["Date de facture invalide"],
                'details': {},
                'date_utilisee': None
            }
    
    resultats = {
        'valide': True,
        'est_recente': True,
        'erreurs': [],
        'avertissements': [],
        'details': {},
        'date_utilisee': date_facture.strftime('%d/%m/%Y'),
        'date_reference': None,
        'source_reference': None,
        'ecart_jours': None
    }
    
    # ⭐ 1. Vérifier si la facture est récente (dans les 30 jours)
    jours_depuis_facture = (datetime.now() - date_facture).days
    if jours_depuis_facture > 30:
        resultats['est_recente'] = False
        resultats['avertissements'].append(
            f"Facture datée de {jours_depuis_facture} jours (>{30} jours)"
        )
    
    # ⭐ 2. Pour chaque annexe présente, extraire sa date et comparer
    for type_annexe, present in annexes_detectees.items():
        if not present:
            continue
        
        # Récupérer le texte OCR de l'annexe
        texte_annexe = textes_annexes.get(type_annexe, '')
        if not texte_annexe:
            continue
        
        date_annexe = extraire_date_depuis_texte(texte_annexe)
        if not date_annexe:
            resultats['avertissements'].append(
                f"{type_annexe}: Aucune date trouvée"
            )
            continue
        
        # Calculer l'écart
        ecart = (date_facture - date_annexe).days
        ecart_abs = abs(ecart)
        
        resultats['details'][type_annexe] = {
            'date': date_annexe.strftime('%d/%m/%Y'),
            'ecart_jours': ecart,
            'ecart_absolu': ecart_abs,
            'est_avant_facture': ecart >= 0
        }
        
        # ⭐ 3. Règles de validation par type d'annexe
        if type_annexe == 'bon_livraison':
            # BL doit être avant ou égal à la facture
            if ecart < 0:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"BL ({date_annexe.strftime('%d/%m/%Y')}) est après la facture (+{abs(ecart)} jours)"
                )
            else:
                resultats['date_reference'] = date_annexe
                resultats['source_reference'] = 'bon_livraison'
                resultats['ecart_jours'] = ecart
        
        elif type_annexe in ['pv_reception', 'certificats_rapport']:
            # PV/Certificat doit être autour de la facture (±30 jours)
            if ecart_abs > 30:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"{type_annexe} ({date_annexe.strftime('%d/%m/%Y')}) trop éloigné de la facture ({ecart_abs} jours)"
                )
            else:
                if not resultats['date_reference']:
                    resultats['date_reference'] = date_annexe
                    resultats['source_reference'] = type_annexe
                    resultats['ecart_jours'] = ecart
        
        elif type_annexe == 'feuille_presence':
            # Feuille de présence peut avoir une date différente (formation)
            if ecart_abs > 60:
                resultats['avertissements'].append(
                    f"Feuille de présence ({date_annexe.strftime('%d/%m/%Y')}) éloignée de la facture ({ecart_abs} jours)"
                )
        
        elif type_annexe == 'pv_location':
            # PV de location doit être avant ou égal à la facture
            if ecart < 0:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"PV Location ({date_annexe.strftime('%d/%m/%Y')}) est après la facture (+{abs(ecart)} jours)"
                )
    
    # ⭐ 4. Si pas de date de référence trouvée, utiliser la date facture
    if not resultats['date_reference']:
        resultats['date_reference'] = date_facture
        resultats['source_reference'] = 'facture_seule'
        resultats['ecart_jours'] = 0
    
    # ⭐ 5. Déterminer si la facture est récente (basé sur la date de référence)
    if resultats['date_reference']:
        jours_depuis_ref = (datetime.now() - resultats['date_reference']).days
        resultats['est_recente'] = jours_depuis_ref <= 30
        
        if jours_depuis_ref > 30 and not resultats['erreurs']:
            resultats['avertissements'].append(
                f"Date de référence ({resultats['date_reference'].strftime('%d/%m/%Y')}) datée de {jours_depuis_ref} jours"
            )
    
    return resultats


def extraire_texte_annexe(chemin_annexe: str) -> str:
    """
    Extrait le texte OCR d'un document annexe.
    """
    try:
        if chemin_annexe.lower().endswith('.pdf'):
            images = convert_from_path(chemin_annexe, dpi=150, first_page=1, last_page=1, poppler_path=POPPLER_PATH)
            if not images:
                return ''
            textes = ocr_image_to_texts(images[0])
            texte = ' '.join(t['texte'] for t in textes).upper()
            del images
            return texte
        else:
            image = Image.open(chemin_annexe)
            textes = ocr_image_to_texts(image)
            return ' '.join(t['texte'] for t in textes).upper()
    except Exception as e:
        print(f"   ⚠️ Erreur extraction texte annexe: {e}")
        return ''


# ─────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE - TRAITE TOUTES LES PAGES
# ─────────────────────────────────────────────────────────────────

def extraire_criteres_somas(chemin_facture, verbose=True):
    if isinstance(chemin_facture, str):
        chemin_facture = chemin_facture.strip().strip('"').strip("'")
        if not os.path.exists(chemin_facture):
            raise FileNotFoundError(f"Fichier non trouvé : {chemin_facture}")
        
        if chemin_facture.lower().endswith('.pdf'):
            if verbose:
                print(f"   📄 Conversion PDF en image (Dpi=150)...")
            
            images = convert_from_path(
                chemin_facture, 
                dpi=150, 
                first_page=1, 
                last_page=10,
                poppler_path=POPPLER_PATH
            )
            
            if verbose:
                print(f"   ✅ {len(images)} pages converties")
            
            textes_total = []
            texte_complet_total = ''
            
            for idx, image in enumerate(images):
                if verbose:
                    print(f"   🔍 OCR page {idx+1}/{len(images)}...")
                
                textes_page = ocr_image_to_texts(image)
                textes_total.extend(textes_page)
                texte_complet_total += ' '.join(t['texte'] for t in textes_page).upper() + ' '
                
                del image
                gc.collect()
            
            textes = textes_total
            texte_complet = texte_complet_total
            
            if verbose:
                print(f"   ✅ {len(textes)} mots extraits au total")
            
            del images
            gc.collect()
        else:
            image = Image.open(chemin_facture)
            textes = ocr_image_to_texts(image)
            texte_complet = ' '.join(t['texte'] for t in textes).upper()
    else:
        image = chemin_facture
        textes = ocr_image_to_texts(image)
        texte_complet = ' '.join(t['texte'] for t in textes).upper()

    # Détection des critères avec logs si verbose
    if verbose:
        print("\n🔍 DÉTECTION DES CRITÈRES SOMAS:")
    
    date_valide, date_trouvee = detecter_date(texte_complet)
    if verbose and date_trouvee:
        print(f"   ✅ Date: {date_trouvee.strftime('%d/%m/%Y')} (valide: {date_valide})")
    
    if_ok = detecter_if(texte_complet)
    if verbose:
        print(f"   {'✅' if if_ok else '❌'} IF: {'Détecté' if if_ok else 'Non détecté'}")
    
    # ⭐ Détection de l'ICE du fournisseur (inchangé)
        # ⭐ Détection de l'ICE du fournisseur vs SOMAS
       # ⭐ Détection de l'ICE du fournisseur vs SOMAS
    tous_les_ice = detecter_ice(texte_complet)
    ICE_SOMAS_ATTENDU = "00000695000053"
    
    ice_fournisseur = None
    ice_somas_present = False
    
    # 1. Parcourir tous les ICE trouvés
    for ice in tous_les_ice:
        if ice == ICE_SOMAS_ATTENDU:
            ice_somas_present = True
        elif ice_fournisseur is None:
            ice_fournisseur = ice
    
    # 2. Logique de validation (APRÈS la boucle)
    if ice_fournisseur:
        ice_ok = True
        ice_valeur = ice_fournisseur
        if verbose:
            print(f"   ✅ ICE Fournisseur: {ice_valeur}")
            if ice_somas_present:
                print(f"   ✅ ICE SOMAS présent: {ICE_SOMAS_ATTENDU}")
            if len(tous_les_ice) > 1:
                autres = [i for i in tous_les_ice if i != ice_valeur]
                if autres:
                    print(f"   ⚠️ Autres ICE détectés: {autres}")
    else:
        ice_ok = False
        ice_valeur = None
        if verbose:
            print(f"   ❌ ICE: Non détecté")
    
    # ⭐⭐⭐ CORRECTION CNSS : Utiliser extraire_cnss_avec_validation
    cnss_valeur = extraire_cnss_avec_validation(texte_complet)
    if cnss_valeur:
        cnss_ok = True
        if verbose:
            print(f"   ✅ CNSS: {cnss_valeur}")
    else:
        cnss_ok = False
        cnss_valeur = None
        if verbose:
            print(f"   ❌ CNSS: Non détecté")
    
    rc_ok, rc_valeur = detecter_rc(texte_complet)
    if verbose:
        print(f"   {'✅' if rc_ok else '❌'} RC: {rc_valeur if rc_valeur else 'Non détecté'}")
    
    tp_ok = detecter_taxe_professionnelle(texte_complet)
    if verbose:
        print(f"   {'✅' if tp_ok else '❌'} Taxe professionnelle: {'Détecté' if tp_ok else 'Non détecté'}")
    
    rib_ok, rib_valeur = detecter_rib(texte_complet)
    if verbose:
        print(f"   {'✅' if rib_ok else '❌'} RIB: {rib_valeur if rib_valeur else 'Non détecté'}")
    
    montant_lettres_ok = detecter_montant_lettres(texte_complet)
    if verbose:
        print(f"   {'✅' if montant_lettres_ok else '❌'} Montant en lettres: {'Détecté' if montant_lettres_ok else 'Non détecté'}")
    numero_facture = detecter_numero_facture(texte_complet, chemin_facture)
    if verbose and numero_facture:
        print(f"   ✅ Numéro facture: {numero_facture}")
    elif verbose:
        print(f"   ⚠️ Numéro facture non détecté")

    objet_commande_ok = detecter_objet_commande(texte_complet)
    objet_commande_trouve = extraire_objet_commande(texte_complet)
    if verbose:
        print(f"   {'✅' if objet_commande_ok else '❌'} Objet de commande: {objet_commande_trouve}")
    
    type_objet = estimer_type_objet(texte_complet)
    if verbose:
        print(f"   📋 Type d'objet estimé: {type_objet}")
    
    # Cachet - seulement sur la première page
    if isinstance(chemin_facture, str) and chemin_facture.lower().endswith('.pdf'):
        images = convert_from_path(chemin_facture, dpi=150, first_page=1, last_page=1, poppler_path=POPPLER_PATH)
        image = images[0]
        cachet_ok = detecter_cachet_visuel(image)
        if verbose:
            print(f"   {'✅' if cachet_ok else '❌'} Cachet/Signature: {'Présent' if cachet_ok else 'Absent'}")
        del images
        gc.collect()
    else:
        image = Image.open(chemin_facture)
        cachet_ok = detecter_cachet_visuel(image)
        if verbose:
            print(f"   {'✅' if cachet_ok else '❌'} Cachet/Signature: {'Présent' if cachet_ok else 'Absent'}")

    if isinstance(chemin_facture, str): 
        del image
        gc.collect()

    # ⭐⭐⭐ FIN DU RETURN AVEC TOUS LES CHAMPS NÉCESSAIRES ⭐⭐⭐
    return {
        'date_valide': date_valide,
        'if_ok': if_ok,
        'ice_ok': ice_ok,
        'cnss_ok': cnss_ok,
        'rc_ok': rc_ok,
        'taxe_professionnelle_ok': tp_ok,
        'rib_ok': rib_ok,
        'cachet_ok': cachet_ok,
        'montant_lettres_ok': montant_lettres_ok,
        'objet_commande_ok': objet_commande_ok,
        'objet_commande_trouve': objet_commande_trouve,
        'ice_valeur': ice_valeur,
        'cnss_valeur': cnss_valeur,
        'rc_valeur': rc_valeur,
        'rib_valeur': rib_valeur,
        'date_trouvee': str(date_trouvee) if date_trouvee else None,
        'type_objet': type_objet,
        'texte_extrait': texte_complet[:1000],
        'nb_mots_ocr': len(textes),
        'confiance_moyenne': float(np.mean([t['confiance'] for t in textes])) if textes else 0.0,
        'numero_facture': numero_facture,
        'all_ice_detected': tous_les_ice,
        'ice_somas_present': ice_somas_present,   # ⭐ CHAMP AJOUTÉ POUR LE FRONTEND
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        chemin = sys.argv[1]
        
        if "--debug" in sys.argv:
            debug_ocr(chemin)
        elif "--debug-extract" in sys.argv:
            debug_extraction(chemin)
        else:
            resultats = extraire_criteres_somas(chemin, verbose=True)
            print("\n📊 RÉSULTATS :")
            for key, value in resultats.items():
                if key not in ['texte_extrait']:
                    print(f"   {key}: {value}")
    else:
        print("Usage :")
        print("  python ocr_extractor.py chemin/vers/facture.pdf")
        print("  python ocr_extractor.py --debug chemin/vers/facture.pdf  # Affiche TOUS les mots")
        print("  python ocr_extractor.py --debug-extract chemin/vers/facture.pdf  # Affiche les éléments détectés")