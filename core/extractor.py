# core/extractor.py - Version avec Gemini Vision directe (UN SEUL APPEL)

import ollama
import json
import os
import re
import difflib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

from core.gemini_vision import extraire_avec_vision_si_besoin, VISION_DISABLED

# Importer votre OCR
from core.ocr_extractor import extraire_criteres_somas

# ⭐ Importer Gemini (avec Vision directe)
from core.gemini_extractor import (
    extraire_objet_avec_gemini,
    extraire_annexes_avec_gemini,
    extraire_objet_et_annexes_avec_vision_directe,
    GEMINI_DISABLED
)

# Configuration
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MODEL_NAME = "phi3:3.8b-instruct"

# ⭐ Variable globale pour stocker le résultat Vision (éviter les appels multiples)
_VISION_RESULT = None

# ════════════════════════════════════════════════════════════════
# 0. FONCTIONS DE VALIDATION DES DATES AVEC LES ANNEXES
# ════════════════════════════════════════════════════════════════

MOIS_MAP = {
    'JANVIER': 1, 'FEVRIER': 2, 'MARS': 3, 'AVRIL': 4, 'MAI': 5, 'JUIN': 6,
    'JUILLET': 7, 'AOUT': 8, 'SEPTEMBRE': 9, 'OCTOBRE': 10, 'NOVEMBRE': 11,
    'DECEMBRE': 12, 'JAN': 1, 'FEV': 2, 'MAR': 3, 'AVR': 4, 'JUN': 6,
    'JUL': 7, 'AOU': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
}


def valider_date_facture_avec_annexes_vision(
    date_facture_str: str,
    dates_annexes: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Valide la date de la facture par rapport aux dates des annexes.
    """
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
                'avertissements': [],
                'details': {},
                'date_utilisee': None,
                'date_reference': None,
                'source_reference': None,
                'ecart_jours': None
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
    
    # ⭐⭐⭐ CORRECTION : NE PAS comparer avec la date du jour
    # On utilise UNIQUEMENT la date de l'annexe comme référence
    # La récence est déterminée par l'écart entre facture et annexe, pas avec aujourd'hui
    
    # Valider chaque annexe
    for type_annexe, info in dates_annexes.items():
        if not info or not info.get('date'):
            continue
        
        date_annexe = info['date']
        ecart = (date_facture - date_annexe).days
        ecart_abs = abs(ecart)
        
        resultats['details'][type_annexe] = {
            'date': date_annexe.strftime('%d/%m/%Y'),
            'ecart_jours': ecart,
            'est_avant_facture': ecart >= 0
        }
        
        # ⭐⭐ Déterminer la récence : écart entre facture et annexe ≤ 30 jours
        if ecart_abs <= 30:
            resultats['est_recente'] = True
            resultats['date_reference'] = date_annexe
            resultats['source_reference'] = type_annexe
            resultats['ecart_jours'] = ecart
        else:
            resultats['est_recente'] = False
            resultats['avertissements'].append(
                f"Écart de {ecart_abs} jours entre la facture et {type_annexe} (>{30} jours)"
            )
        
        # Règles de validation par type d'annexe
        if type_annexe == 'bon_livraison':
            if ecart < 0:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"BL ({date_annexe.strftime('%d/%m/%Y')}) est après la facture (+{abs(ecart)} jours)"
                )
            else:
                if not resultats['date_reference']:
                    resultats['date_reference'] = date_annexe
                    resultats['source_reference'] = 'bon_livraison'
                    resultats['ecart_jours'] = ecart
        
        elif type_annexe in ['pv_reception', 'certificats_rapport']:
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
            if ecart_abs > 60:
                resultats['avertissements'].append(
                    f"Feuille de présence ({date_annexe.strftime('%d/%m/%Y')}) éloignée de la facture ({ecart_abs} jours)"
                )
        
        elif type_annexe == 'pv_location':
            if ecart < 0:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"PV Location ({date_annexe.strftime('%d/%m/%Y')}) est après la facture (+{abs(ecart)} jours)"
                )
    
    # Si pas de date de référence trouvée, utiliser la date facture
    if not resultats['date_reference']:
        resultats['date_reference'] = date_facture
        resultats['source_reference'] = 'facture_seule'
        resultats['ecart_jours'] = 0
        # ⭐ Sans annexe, on ne peut pas déterminer la récence
        resultats['est_recente'] = False
        resultats['avertissements'].append("Aucune annexe pour déterminer la récence")
    
    return resultats


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


def extraire_texte_annexe(chemin_annexe: str) -> str:
    """
    Extrait le texte OCR d'un document annexe (PDF ou image).
    """
    try:
        if chemin_annexe.lower().endswith('.pdf'):
            from pdf2image import convert_from_path
            images = convert_from_path(chemin_annexe, dpi=150, first_page=1, last_page=1)
            if not images:
                return ''
            from core.ocr_extractor import ocr_image_to_texts
            textes = ocr_image_to_texts(images[0])
            texte = ' '.join(t['texte'] for t in textes).upper()
            del images
            return texte
        else:
            from PIL import Image
            from core.ocr_extractor import ocr_image_to_texts
            image = Image.open(chemin_annexe)
            textes = ocr_image_to_texts(image)
            return ' '.join(t['texte'] for t in textes).upper()
    except Exception as e:
        print(f"   ⚠️ Erreur extraction texte annexe: {e}")
        return ''


def extraire_date_annexe(chemin_annexe: str) -> Dict[str, Any]:
    """
    Extrait la date d'un document annexe et retourne des infos détaillées.
    """
    try:
        texte = extraire_texte_annexe(chemin_annexe)
        if not texte:
            return {
                'date': None,
                'date_str': None,
                'texte_extrait': '',
                'source': 'inconnu',
                'erreur': 'Texte OCR vide'
            }
        
        type_doc = 'inconnu'
        if 'BON DE LIVRAISON' in texte or 'BL' in texte:
            type_doc = 'bon_livraison'
        elif 'PV DE RECEPTION' in texte or 'PROCES VERBAL' in texte:
            type_doc = 'pv_reception'
        elif 'CERTIFICAT' in texte:
            type_doc = 'certificat'
        elif 'RAPPORT' in texte:
            type_doc = 'rapport'
        elif 'FEUILLE DE PRESENCE' in texte:
            type_doc = 'feuille_presence'
        
        date_obj = extraire_date_depuis_texte(texte)
        
        return {
            'date': date_obj,
            'date_str': date_obj.strftime('%d/%m/%Y') if date_obj else None,
            'texte_extrait': texte[:500],
            'source': type_doc,
            'erreur': None if date_obj else 'Aucune date trouvée'
        }
    except Exception as e:
        return {
            'date': None,
            'date_str': None,
            'texte_extrait': '',
            'source': 'inconnu',
            'erreur': str(e)
        }


def valider_date_facture_avec_annexes(
    date_facture_str: str,
    annexes_detectees: Dict[str, bool],
    textes_annexes: Dict[str, str]
) -> Dict[str, Any]:
    """
    Valide la date de la facture par rapport aux annexes.
    """
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
                'avertissements': [],
                'details': {},
                'date_utilisee': None,
                'date_reference': None,
                'source_reference': None,
                'ecart_jours': None,
                'dates_annexes': {}
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
        'ecart_jours': None,
        'dates_annexes': {}
    }
    
    jours_depuis_facture = (datetime.now() - date_facture).days
    if jours_depuis_facture > 30:
        resultats['est_recente'] = False
        resultats['avertissements'].append(
            f"Facture datée de {jours_depuis_facture} jours (>{30} jours)"
        )
    elif jours_depuis_facture < -30:
        resultats['est_recente'] = False
        resultats['avertissements'].append(
            f"Facture dans le futur ({abs(jours_depuis_facture)} jours)"
        )
    
    for type_annexe, present in annexes_detectees.items():
        if not present:
            continue
        
        texte_annexe = textes_annexes.get(type_annexe, '')
        if not texte_annexe:
            resultats['avertissements'].append(
                f"{type_annexe}: Texte OCR non disponible"
            )
            continue
        
        date_annexe = extraire_date_depuis_texte(texte_annexe)
        
        resultats['dates_annexes'][type_annexe] = {
            'date': date_annexe.strftime('%d/%m/%Y') if date_annexe else None,
            'trouvee': date_annexe is not None
        }
        
        if not date_annexe:
            resultats['avertissements'].append(
                f"{type_annexe}: Aucune date trouvée"
            )
            continue
        
        ecart = (date_facture - date_annexe).days
        ecart_abs = abs(ecart)
        
        resultats['details'][type_annexe] = {
            'date': date_annexe.strftime('%d/%m/%Y'),
            'ecart_jours': ecart,
            'ecart_absolu': ecart_abs,
            'est_avant_facture': ecart >= 0
        }
        
        if type_annexe == 'bon_livraison':
            if ecart < 0:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"BL ({date_annexe.strftime('%d/%m/%Y')}) est après la facture (+{abs(ecart)} jours)"
                )
            else:
                if not resultats['date_reference']:
                    resultats['date_reference'] = date_annexe
                    resultats['source_reference'] = 'bon_livraison'
                    resultats['ecart_jours'] = ecart
        
        elif type_annexe in ['pv_reception', 'certificats_rapport']:
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
            if ecart_abs > 60:
                resultats['avertissements'].append(
                    f"Feuille de présence ({date_annexe.strftime('%d/%m/%Y')}) éloignée de la facture ({ecart_abs} jours)"
                )
        
        elif type_annexe == 'pv_location':
            if ecart < 0:
                resultats['valide'] = False
                resultats['erreurs'].append(
                    f"PV Location ({date_annexe.strftime('%d/%m/%Y')}) est après la facture (+{abs(ecart)} jours)"
                )
    
    if not resultats['date_reference']:
        resultats['date_reference'] = date_facture
        resultats['source_reference'] = 'facture_seule'
        resultats['ecart_jours'] = 0
    
    if resultats['date_reference']:
        jours_depuis_ref = (datetime.now() - resultats['date_reference']).days
        if jours_depuis_ref > 30:
            resultats['est_recente'] = False
            if not resultats['erreurs']:
                resultats['avertissements'].append(
                    f"Date de référence ({resultats['date_reference'].strftime('%d/%m/%Y')}) datée de {jours_depuis_ref} jours"
                )
        elif jours_depuis_ref < -30:
            resultats['est_recente'] = False
            if not resultats['erreurs']:
                resultats['avertissements'].append(
                    f"Date de référence dans le futur ({abs(jours_depuis_ref)} jours)"
                )
    
    return resultats


# ════════════════════════════════════════════════════════════════
# 1. DÉTECTION DE LA NATURE DE L'OPÉRATION
# ════════════════════════════════════════════════════════════════

def detecter_nature_operation(objet_commande: str, texte_complet: str) -> str:
    """
    Détecte la nature de l'opération à partir de l'objet et du texte.
    Retourne: 'acquisition', 'prestation_assistance', 'etude', 'location', 'formation', 'general'
    """
    
    if not objet_commande:
        objet_commande = ""
    
    texte_complet_lower = texte_complet.lower()
    objet_lower = objet_commande.lower()
    
    natures = {
        'acquisition': [
            'fourniture', 'achat', 'approvisionnement', 'réapprovisionnement',
            'acquisition', 'équipement', 'matériel', 'hardware',
            'ordinateur', 'imprimante', 'serveur', 'pdr'
        ],
        'prestation_assistance': [
            'contrôle', 'intervention', 'paramétrage', 'développement',
            'diagnostic', 'épreuve', 'installation', 'peinture',
            'prestation', 'assistance', 'maintenance', 'réparation',
            'support', 'conseil'
        ],
        'formation': [
            'formation', 'formateur', 'stage', 'apprentissage',
            'équipier', 'première intervention', 'habilitation'
        ],
        'etude': [
            'étude', 'analyse', 'diagnostic', 'expertise',
            'consulting', 'recherche', 'conception', 'plan'
        ],
        'location': [
            'location', 'leasing', 'vehicule', 'voiture',
            'engin', 'camion', 'remorque'
        ]
    }
    
    for nature, keywords in natures.items():
        for keyword in keywords:
            if keyword in objet_lower or keyword in texte_complet_lower:
                print(f"   📋 Nature détectée: {nature} (mot-clé: '{keyword}')")
                return nature
    
    if not objet_commande or objet_commande == 'Non détecté':
        return 'general'
    
    return 'general'


# ════════════════════════════════════════════════════════════════
# 2. ANNEXES OBLIGATOIRES PAR NATURE
# ════════════════════════════════════════════════════════════════

def get_annexes_obligatoires_par_nature(nature: str, type_fournisseur: str = None) -> Dict[str, bool]:
    """
    Retourne les annexes obligatoires selon la nature de l'opération et le type de fournisseur.
    """
    
    annexes = {
        "attestation_rib": False,
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False
    }
    
    # ⭐ SI NOUVEAU FOURNISSEUR : Attestation RIB OBLIGATOIRE
    if type_fournisseur == 'Nouveauf':
        annexes['attestation_rib'] = True
        print(f"   📋 Nouveau fournisseur: Attestation RIB OBLIGATOIRE")
    
    if nature == 'acquisition':
        annexes['bon_livraison'] = True
        print(f"   📋 Acquisition d'équipements: Bon de livraison obligatoire")
        
    elif nature == 'prestation_assistance':
        annexes['pv_reception'] = True
        print(f"   📋 Prestation/Assistance: PV de réception obligatoire")
        
    elif nature == 'etude':
        print(f"   📋 Étude: Certificats/Rapport à détecter par l'IA UNIQUEMENT")
        
    elif nature == 'location':
        annexes['pv_location'] = True
        print(f"   📋 Location: PV de location obligatoire")
        
    elif nature == 'formation':
        annexes['feuille_presence'] = True
        annexes['pv_reception'] = False
        print(f"   📋 Formation: Feuille de présence obligatoire")
        print(f"   📋 Formation: PV de réception NON obligatoire")
    
    return annexes


# ════════════════════════════════════════════════════════════════
# 3. DÉTECTION DIRECTE DU CERTIFICAT
# ════════════════════════════════════════════════════════════════

def detecter_certificat_direct(texte_complet: str) -> bool:
    """
    Détection directe d'un certificat dans le texte.
    """
    texte_upper = texte_complet.upper()
    
    mots_cles_exiges = [
        'CERTIFICAT', 'RAPPORT', 'VERIFICATION',
        'ANNUEL', 'ORGANISME VERIFICATEUR'
    ]
    
    for mot in mots_cles_exiges:
        if mot in texte_upper:
            print(f"   ✅ Mot-clé trouvé: {mot}")
            return True
    
    patterns = [
        r'CERTIFICAT\s+ANNUEL',
        r'CERTIFICAT\s+DE\s+VERIFICATION',
        r'CERTIFICAT\s+DE\s+VERIFICATIONIS',
        r'VERIFICATIONIS\s+D\'INSTALLATIONS',
        r'RAPPORT\s+DE\s+VERIFICATION',
        r'VERIFICATION\s+ANNUELLE',
        r'ORGANISME\s+VERIFICATEUR',
        r'CERTIFICAT\s+DE\s+CONFORMITE',
        r'ATTESTATION\s+DE\s+CONFORMITE',
        r'RAPPORT\s+D[ÉE]TAILL[ÉE]',
        r'CERTIFICAT\s+D\'INSTALLATIONS',
        r'CERTIFICAT\s+D\'INSTALLATIONS\s+ELECTRIQUES',
        r'VERIFICATION\s+ANNUELLE\s+D\'INSTALLATIONS',
        r'CERTIFICAT\s+ANNUEL\s+DE\s+VERIFICATION',
        r'CERTIFICAT\s+DE\s+CONTROLE',
        r'CERTIFICAT\s+ANNUEL\s+DE\s+VERIFICATIONIS',
        r'VERIFICATIONIS\s+D\'INSTALLATIONS\s+ELECTRIQUES',
        r'CERTIFICAT.*VERIFICATION.*ELECTRIQUES',
        r'CERTIFICAT.*ANNUEL.*VERIFICATION',
    ]
    
    for pattern in patterns:
        if re.search(pattern, texte_complet, re.IGNORECASE):
            print(f"   ✅ Pattern trouvé: {pattern}")
            return True
    
    return False


# ════════════════════════════════════════════════════════════════
# ⭐ NOUVEAU : FILTRE ANTI-FAUX POSITIFS POUR ATTESTATION RIB
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# ⭐ FILTRE ANTI-FAUX POSITIFS POUR ATTESTATION RIB
# ════════════════════════════════════════════════════════════════

def filtrer_attestation_rib(annexes_detectees: Dict[str, bool], texte_complet: str, type_fournisseur: str = None) -> Dict[str, bool]:
    """
    Filtre les faux positifs pour l'attestation RIB.
    
    RÈGLE ABSOLUE : 
    - L'attestation RIB est UNIQUEMENT recherchée si le fournisseur est un NOUVEAU FOURNISSEUR
    - Si le fournisseur n'est pas nouveau (type_fournisseur != 'Nouveauf'), on force à False
    - Pour un nouveau fournisseur, on vérifie si une attestation RIB est présente
    """
    
    resultat = annexes_detectees.copy()
    
    # ⭐⭐⭐ RÈGLE ABSOLUE : Si ce n'est pas un nouveau fournisseur, on force attestation_rib à False ⭐⭐⭐
    if type_fournisseur != 'Nouveauf':
        if resultat.get('attestation_rib', False):
            print(f"   🔴 Fournisseur NON nouveau: attestation_rib forcée à False")
            resultat['attestation_rib'] = False
        return resultat
    
    # ⭐⭐⭐ ICI, on est en mode "Nouveau fournisseur" ⭐⭐⭐
    if not annexes_detectees.get('attestation_rib', False):
        print(f"   ⚠️ Nouveau fournisseur: attestation_rib non détectée")
        return resultat
    
    print(f"   🔍 Nouveau fournisseur - Vérification de l'attestation RIB...")
    
    # ⭐ 1. Vérifier si le document contient un TITRE d'attestation RIB
    titres_attestation = [
        "ATTESTATION RIB",
        "ATTESTATION DE RIB", 
        "RELEVÉ D'IDENTITÉ BANCAIRE",
        "RELEVE D'IDENTITE BANCAIRE",
        "ATTESTATION DE RELEVÉ D'IDENTITÉ BANCAIRE",
        "CERTIFICAT RIB",
        "JUSTIFICATIF RIB"
    ]
    
    a_un_titre = False
    for titre in titres_attestation:
        if titre.upper() in texte_complet.upper():
            a_un_titre = True
            print(f"   ✅ Titre trouvé: {titre}")
            break
    
    if a_un_titre:
        print(f"   ✅ Attestation RIB confirmée (titre présent)")
        return resultat
    
    # ⭐ 2. Vérifier si un numéro RIB est présent dans le texte (nouveau fournisseur)
    pattern_rib = r'RIB\s*[:.]?\s*[0-9]{3}\s*[0-9]{3}\s*[0-9]{3}\s*[0-9]{3}\s*[0-9]{3}\s*[0-9]{3}'
    if re.search(pattern_rib, texte_complet, re.IGNORECASE):
        print(f"   ✅ Nouveau fournisseur: RIB présent, attestation_rib conservée")
        return resultat
    else:
        print(f"   ⚠️ Nouveau fournisseur mais aucun RIB trouvé - attestation_rib mise à False")
        resultat['attestation_rib'] = False
        return resultat


# ════════════════════════════════════════════════════════════════
# 4. ENRICHIR LES ANNEXES AVEC LES RÈGLES DE NATURE
# ════════════════════════════════════════════════════════════════

def enrichir_annexes_avec_nature(annexes: Dict[str, bool], nature: str, texte_complet: str, type_fournisseur: str = None) -> Dict[str, bool]:
    """
    Enrichit les annexes détectées avec les règles de la nature.
    """
    
    resultat = annexes.copy()
    
    # ⭐⭐⭐ CORRECTION : NE PAS FORCER attestation_rib à False pour les nouveaux fournisseurs ⭐⭐⭐
    if type_fournisseur == 'Nouveauf':
        # Pour nouveau fournisseur, on GARDE la valeur détectée par Vision
        print(f"   🟢 Nouveau fournisseur: attestation_rib conservée = {resultat.get('attestation_rib', False)}")
    else:
        # Pour les fournisseurs existants, on force à False
        resultat['attestation_rib'] = False
        print(f"   🔴 Fournisseur existant: attestation_rib FORCÉ à False")
    
    if nature == 'formation':
        resultat['pv_reception'] = False
        print(f"   🔴 pv_reception FORCÉ à False (formation - pas obligatoire)")
    
    annexes_obligatoires = get_annexes_obligatoires_par_nature(nature, type_fournisseur)
    
    for key, value in annexes_obligatoires.items():
        if value:
            if key not in ['attestation_rib', 'certificats_rapport']:
                if key == 'pv_reception' and nature == 'formation':
                    continue
                resultat[key] = True
                print(f"   📋 {key} forcé à True (obligatoire pour {nature})")
            elif key == 'attestation_rib' and type_fournisseur == 'Nouveauf': 
                # ⭐ Pour nouveau fournisseur, on GARDE la valeur détectée par Vision
                # Ne pas forcer à True, garder la valeur détectée
                print(f"   📋 attestation_rib détectée par Vision: {resultat.get('attestation_rib', False)}")
    
    print(f"   📋 attestation_rib: {'✅' if resultat.get('attestation_rib') else '❌'}")
    print(f"   📋 bon_livraison: {'✅' if resultat.get('bon_livraison') else '❌'}")
    print(f"   📋 pv_reception: {'✅' if resultat.get('pv_reception') else '❌'}")
    print(f"   📋 pv_location: {'✅' if resultat.get('pv_location') else '❌'}")
    print(f"   📋 feuille_presence: {'✅' if resultat.get('feuille_presence') else '❌'}")
    print(f"   📋 certificats_rapport: {'✅' if resultat.get('certificats_rapport') else '❌'}")
    print(f"   📋 engagement_importation: {'✅' if resultat.get('engagement_importation') else '❌'}")
    print(f"   📋 quittance_douane: {'✅' if resultat.get('quittance_douane') else '❌'}")
    
    return resultat


# ════════════════════════════════════════════════════════════════
# 5. DÉTECTION DU FOURNISSEUR (PHI3)
# ════════════════════════════════════════════════════════════════

def detecter_fournisseur_avec_phi3(
    texte_complet: str,
    resultats_ocr: Dict[str, Any]
) -> Tuple[str, str]:
    """
    phi3 détecte le fournisseur.
    """
    
    if not texte_complet or len(texte_complet) < 100:
        return "Non détecté", None
    
    print(f"   🔍 phi3 analyse toutes les données pour trouver le fournisseur...")
    
    NOMS_EXCLUS = [
        'SOMAS', 'SOCIETE MAROCAINE DE STOCKAGE', 'SO.MA.S',
        'SOCIETE MAROCAINE', 'STE MAROCAINE', 'STE MNE',
        'MOHAMMEDIA', 'MOHAMMADIA', 'CASABLANCA', 'RABAT', 
        'TANGER', 'MARRAKECH', 'FES', 'AGADIR', 'KENITRA',
        'ATTIJARIWAFABANK', 'BMCE', 'BANQUE', 'BANK',
        'MAERSK', 'GLOBITRANS', 'IPS SUPPLY', 'IPS',
        'CLIENT', 'DESTINATAIRE', 'IMPORTATEUR', 'DECLARANT',
        'FOURNISSEUR', 'EMETTEUR', 'EXPEDITEUR', 'SUPPLIER',
        'SERVICE', 'AGENCE', 'BUREAU', 'COMPTABILITE',
        'OO', 'SORT', 'SARTIA', 'SIARTIA', 'SIATRIA',
    ]
    
    checklist = resultats_ocr.get('checklist_somas', {})
    
    ice = checklist.get('ice_valeur', 'Non détecté')
    cnss = checklist.get('cnss_valeur', 'Non détecté')
    
    if not cnss or cnss == "Non détecté" or cnss is None:
        cnss = "NON DÉTECTÉ (aucune CNSS dans le document)"
    
    rc = checklist.get('rc_valeur', 'Non détecté')
    rib = checklist.get('rib_valeur', 'Non détecté')
    if_val = checklist.get('if_valeur', 'Non détecté')
    type_objet = checklist.get('type_objet', 'Non détecté')
    objet_commande = checklist.get('objet_commande_trouve', 'Non détecté')
    cachet = '✅ Présent' if checklist.get('cachet_ok') else '❌ Absent'
    
    noms_avec_identifiants = []
    patterns = [
        r'([A-Z][A-Z\s]{3,60}?)\s+RC\s*[:]?\s*\d+',
        r'([A-Z][A-Z\s]{3,60}?)\s+ICE\s*[:]?\s*\d+',
        r'([A-Z][A-Z\s]{3,60}?)\s+CNSS\s*[:]?\s*\d+',
        r'([A-Z][A-Z\s]{3,60}?)\s+PATENTE\s*[:]?\s*\d+',
        r'([A-Z][A-Z\s]{3,60}?)\s+IF\s*[:]?\s*\d+',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, texte_complet, re.IGNORECASE)
        for match in matches:
            nom = match.strip() if isinstance(match, str) else match[0].strip()
            if nom and len(nom) > 4:
                est_exclu = False
                for excl in NOMS_EXCLUS:
                    if excl.upper() in nom.upper() or nom.upper() in excl.upper():
                        est_exclu = True
                        break
                if not est_exclu:
                    if nom not in noms_avec_identifiants:
                        noms_avec_identifiants.append(nom)
    
    entete = '\n'.join(texte_complet.split('\n')[:20])
    noms_entete = re.findall(r'\b([A-Z][A-Z\s]{4,50}?)\b', entete)
    noms_entete_filtres = []
    for nom in noms_entete:
        if len(nom) > 4:
            est_exclu = False
            for excl in NOMS_EXCLUS:
                if excl.upper() in nom.upper() or nom.upper() in excl.upper():
                    est_exclu = True
                    break
            if not est_exclu:
                noms_entete_filtres.append(nom)
    noms_entete = noms_entete_filtres
    
    prompt = f"""
    Tu es un expert en extraction de données de factures marocaines.

    ⭐ TÂCHE : Identifie le nom EXACT du FOURNISSEUR.

    📋 INFORMATIONS OCR :
    - ICE : {ice}
    - CNSS : {cnss}
    - RC : {rc}
    - RIB : {rib}
    - IF : {if_val}
    - Type d'objet : {type_objet}
    - Objet de commande : {objet_commande}
    - Cachet : {cachet}

    🔍 IMPORTANT : Si CNSS = "NON DÉTECTÉ (aucune CNSS dans le document)", ne pas inventer de valeur.

    🏢 NOMS AVEC IDENTIFIANTS : {', '.join(noms_avec_identifiants) if noms_avec_identifiants else 'Aucun'}
    📄 NOMS DANS L'EN-TÊTE : {', '.join(noms_entete) if noms_entete else 'Aucun'}

    🔍 RÈGLES :
    1️⃣ L'entreprise qui a SES PROPRES identifiants (ICE, CNSS, RC)
    2️⃣ Le fournisseur est dans l'en-tête
    3️⃣ SOMAS = CLIENT, PAS fournisseur

    📄 TEXTE COMPLET : {texte_complet[:2000]}

    FOURNISSEUR EXACT :
    """
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.0, 'num_predict': 100}
        )
        
        fournisseur = response['message']['content'].strip()
        fournisseur = re.sub(r'^["\']+|["\']+$', '', fournisseur)
        fournisseur = re.sub(r'\s+', ' ', fournisseur)
        
        if fournisseur and fournisseur != "Non détecté":
            if fournisseur in texte_complet:
                est_exclu = False
                for excl in NOMS_EXCLUS:
                    if excl.upper() in fournisseur.upper() or fournisseur.upper() in excl.upper():
                        est_exclu = True
                        break
                if not est_exclu:
                    print(f"   ✅ Fournisseur identifié: {fournisseur}")
                    return fournisseur, 'phi3'
            
    except Exception as e:
        print(f"   ⚠️ Erreur phi3: {e}")
    
    if noms_avec_identifiants:
        for nom in sorted(noms_avec_identifiants, key=len, reverse=True):
            if ' ' in nom and len(nom) > 5:
                return nom, 'fallback_identifiant'
    
    if noms_entete:
        for nom in sorted(noms_entete, key=len, reverse=True):
            if ' ' in nom and len(nom) > 5:
                return nom, 'fallback_entete'
    
    return "Non détecté", None


# ════════════════════════════════════════════════════════════════
# 6. DÉTECTION DE L'OBJET DE COMMANDE
# ════════════════════════════════════════════════════════════════

PROMPT_OBJET = """Tu es un expert en extraction de données de factures marocaines.

TÂCHE : trouve l'objet de la commande / de la prestation facturée.

OÙ LE CHERCHER (par ordre de priorité) :
1. Une ligne "OBJET :" ou "PRESTATION :"
2. La colonne "DESIGNATION" / "Désignation" / "Description" du tableau des articles
3. Le titre ou l'intitulé principal de la facture

RÈGLE ABSOLUE :
- Recopie le texte EXACTEMENT comme il apparaît
- N'invente rien, ne résume pas
- Si plusieurs objets, prends le premier

TEXTE OCR DE LA FACTURE :
{texte}

Réponds UNIQUEMENT avec un objet JSON :
{
  "objet": "texte exact recopié, ou null si non trouvé",
  "confiance": "haute" | "moyenne" | "faible",
  "indice": "le court passage du texte qui contient cet objet"
}
"""

_STOP_LABELS = (
    r'QUANTIT[ÉE]|PRIX|MONTANT|TOTAL|UNIT[ÉE]|TVA|'
    r'V\.?\s*R[ÉE]F|N\.?\s*R[ÉE]F|R[ÉE]F[ÉE]RENCE|'
    r'BC\s*N[°O]|BON\s*DE\s*COMMANDE|CONTRAT\s*N[°O]|'
    r'R\.?\s*BUDG[ÉE]TAIRE|DATE\s*:|ICE|IF\s*:|RC\s*:'
)


def _normaliser(s: str) -> str:
    s = s.upper()
    s = re.sub(r"\s+", " ", s)
    remplacements = str.maketrans("ÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ", "AAAEEEEIIOOUUUC")
    return s.translate(remplacements).strip()


def _apparait_dans_texte(candidat: str, texte_complet: str, seuil: float = 0.80) -> bool:
    if not candidat or len(candidat) < 4:
        return False
    candidat_n = _normaliser(candidat)
    texte_n = _normaliser(texte_complet)
    if candidat_n in texte_n:
        return True
    fenetre = len(candidat_n) + 8
    for i in range(0, max(1, len(texte_n) - fenetre)):
        segment = texte_n[i:i + fenetre]
        if difflib.SequenceMatcher(None, candidat_n, segment).ratio() >= seuil:
            return True
    return False


def _ressemble_a_un_objet(candidat: str) -> bool:
    if not candidat:
        return False
    lettres = sum(c.isalpha() for c in candidat)
    return lettres >= 4


def _detecter_objet_phi3(texte_complet: str) -> Tuple[Optional[str], str]:
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{'role': 'user', 'content': PROMPT_OBJET.format(texte=texte_complet)}],
            options={'temperature': 0.0, 'num_predict': 200},
        )
        content = response['message']['content'].strip()

        if '```json' in content:
            start = content.find('```json') + 7            
            end = content.find('```', start)
            json_str = content[start:end].strip()
        elif '{' in content:
            start = content.find('{')
            end = content.rfind('}') + 1
            json_str = content[start:end]
        else:
            json_str = content

        donnees = json.loads(json_str)
        objet = (donnees.get('objet') or '').strip()
        confiance = donnees.get('confiance', 'faible')
        indice = donnees.get('indice', '')

        if not objet or objet.lower() in ('null', 'non détecté', 'non detecte'):
            return None, 'phi3_vide'

        if not _ressemble_a_un_objet(objet):
            return None, 'phi3_rejete_format'

        if not _apparait_dans_texte(objet, texte_complet):
            print(f"   ⚠️ Objet '{objet}' introuvable dans le texte source")
            return None, 'phi3_rejete_hallucination'

        return objet, 'phi3'

    except Exception as e:
        print(f"   ⚠️ Erreur phi3: {e}")

    return None, 'phi3_erreur'


def _extraire_apres_label(texte: str, label_pattern: str) -> Optional[str]:
    pattern = rf'{label_pattern}\s*[:\s]*(.+?)(?=\s*(?:{_STOP_LABELS})|$)'
    for match in re.finditer(pattern, texte, re.IGNORECASE):
        candidat = match.group(1).strip()
        candidat = re.sub(r'\s+', ' ', candidat)
        candidat = re.sub(r'^[:\s.-]+', '', candidat)
        candidat = re.sub(r'[:\s.-]+$', '', candidat)
        
        if 4 <= len(candidat) <= 150 and _ressemble_a_un_objet(candidat):
            if not re.match(r'^[\d\s,\.]+$', candidat):
                return candidat
    
    if 'DESIGNATION' in texte.upper() or 'DÉSIGNATION' in texte.upper():
        pattern_tableau = r'(?:DESIGNATION|D[ÉE]SIGNATION)\s*([A-Za-zÀ-ÿ\s\-\.\,]{10,150}?)(?=\s*\d+[\.,]?\d*)'
        match = re.search(pattern_tableau, texte, re.IGNORECASE)
        if match:
            candidat = match.group(1).strip()
            candidat = re.sub(r'\s+', ' ', candidat)
            if 4 <= len(candidat) <= 150 and _ressemble_a_un_objet(candidat):
                return candidat
    
    return None


def _detecter_objet_regex(texte_complet: str) -> Tuple[Optional[str], str]:
    for label, source in [
        (r'OBJET', 'regex_objet'),
        (r'PRESTATION', 'regex_prestation'),
        (r'D[ÉE]SIGNATION', 'regex_designation'),
        (r'DESCRIPTION', 'regex_description'),
    ]:
        resultat = _extraire_apres_label(texte_complet, label)
        if resultat:
            return resultat, source
    
    pattern_tableau = r'(?:DESIGNATION|D[ÉE]SIGNATION)\s*([A-Za-zÀ-ÿ\s\-\.\,]{10,150}?)(?=\s*\d+[\.,]?\d*|\s*[QP]rix|\s*Montant)'
    match = re.search(pattern_tableau, texte_complet, re.IGNORECASE)
    if match:
        candidat = match.group(1).strip()
        candidat = re.sub(r'\s+', ' ', candidat)
        if 4 <= len(candidat) <= 150 and _ressemble_a_un_objet(candidat):
            return candidat, 'regex_tableau'
    
    return None, 'regex_non_trouve'


# ════════════════════════════════════════════════════════════════
# 7. DÉTECTION DES DOCUMENTS ANNEXES (VERSION SIMPLIFIÉE - UNIQUEMENT VISION)
# ════════════════════════════════════════════════════════════════

def detecter_annexes_avec_fallback(
    texte_complet: str, 
    file_path: str, 
    objet: str = None
) -> Dict[str, bool]:
    """
    Détection des annexes : 
    UNIQUEMENT Gemini Vision (pas de fallback, pas de validation)
    """
    
    global _VISION_RESULT
    
    annexes_resultat = {
        "attestation_rib": False,
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False
    }
    
    if _VISION_RESULT and not _VISION_RESULT.get('erreur'):
        if _VISION_RESULT.get('annexes'):
            print(f"   ✅ Utilisation des annexes détectées par Vision")
            annexes_resultat.update(_VISION_RESULT['annexes'])
            return annexes_resultat
    
    print(f"   👁️ Gemini Vision - Détection directe des annexes...")
    try:
        resultat_vision = extraire_objet_et_annexes_avec_vision_directe(file_path)
        if resultat_vision and resultat_vision.get('annexes'):
            print(f"   ✅ Annexes détectées par Vision directe")
            annexes_resultat.update(resultat_vision['annexes'])
            _VISION_RESULT = resultat_vision
    except Exception as e:
        print(f"   ❌ Erreur Vision directe: {e}")
    
    return annexes_resultat


# ════════════════════════════════════════════════════════════════
# 8. RAPPORT DE CONFORMITÉ
# ════════════════════════════════════════════════════════════════

def generer_rapport_conformite(donnees: Dict[str, Any]) -> Dict[str, Any]:
    """Génère un rapport de conformité SOMAS."""
    checklist = donnees.get('checklist_somas', {})
    erreurs = []
    avertissements = []  # ⭐ Nouveau : liste des avertissements
    
    # Récupérer la validation des dates
    validation_dates = donnees.get('validation_dates', {})
    
    # ⭐⭐⭐ CORRECTION : La date est valide SEULEMENT si elle est récente ET cohérente
    if not donnees.get('date_facture'):
        erreurs.append("Date de facture manquante")
    elif validation_dates:
        # Vérifier la cohérence (BL avant facture, etc.)
        if not validation_dates.get('valide', True):
            for err in validation_dates.get('erreurs', []):
                erreurs.append(err)
        # ⭐⭐⭐ Vérifier la récence (écart ≤ 30 jours)
        if not validation_dates.get('est_recente', True):
            erreurs.append("Date de facture non récente (>30 jours d'écart avec l'annexe)")
    
    # ⭐⭐⭐ VÉRIFICATION DE LA DATE D'ÉDITION
    date_edition = checklist.get('date_edition')
    if not date_edition or date_edition == 'null' or date_edition == 'Non détectée':
        # ⭐ Avertissement (pas une erreur bloquante)
        avertissements.append("Date d'édition non détectée - case laissée vide")
        print(f"   ⚠️ AVERTISSEMENT: Date d'édition non détectée")
    
    # ⭐⭐⭐ VÉRIFICATION DE L'ATTESTATION DE RÉGULARITÉ FISCALE
    # L'attestation de régularité fiscale n'est pas un document obligatoire SOMAS
    # mais on signale son absence dans les éléments manquants si elle n'est pas présente
    attestation_fiscale_trouvee = False
    
    # Vérifier si l'attestation fiscale est dans les annexes détectées
    annexes = donnees.get('annexes_detectees', {})
    texte_complet = donnees.get('_metadata', {}).get('texte_complet', '')
    
    # Vérifier dans les annexes
    for doc_name, present in annexes.items():
        if 'attestation' in doc_name.lower() or 'fiscale' in doc_name.lower():
            attestation_fiscale_trouvee = True
            break
    
    # Vérifier dans le texte OCR
    if not attestation_fiscale_trouvee and texte_complet:
        if 'attestation' in texte_complet.lower() and ('fiscale' in texte_complet.lower() or 'régularité' in texte_complet.lower()):
            attestation_fiscale_trouvee = True
    
    # ⭐ Ajouter un avertissement si l'attestation fiscale n'est pas trouvée
    if not attestation_fiscale_trouvee:
        avertissements.append("Demande d'attestation de régularité fiscale non détectée (à vérifier manuellement)")
        print(f"   ⚠️ AVERTISSEMENT: Attestation de régularité fiscale non détectée")
    
    if not donnees.get('objet_commande') or donnees.get('objet_commande') == 'Non détecté':
        erreurs.append("Objet de commande manquant")
    if not checklist.get('ice_ok'):
        erreurs.append("ICE non détecté ou invalide")
    if not checklist.get('cnss_ok'):
        erreurs.append("CNSS non détecté ou invalide")
    if not checklist.get('rc_ok'):
        erreurs.append("RC non détecté ou invalide")
    if not checklist.get('rib_ok'):
        erreurs.append("RIB non détecté ou invalide")
    if not checklist.get('cachet_ok'):
        erreurs.append("Cachet/Signature absent")
    if not checklist.get('taxe_professionnelle_ok'):
        erreurs.append("Taxe professionnelle non détectée")
    
    # ⭐ Ajouter les avertissements aux erreurs (pour les afficher)
    if avertissements:
        erreurs.extend(avertissements)
    
    return {
        'est_conforme': len(erreurs) == 0,
        'nb_erreurs': len(erreurs),
        'nb_avertissements': len(avertissements),
        'erreurs': erreurs,
        'avertissements': avertissements,  # ⭐ Nouveau champ
        'criteres': {
            'champs_obligatoires': 'Conforme' if len(erreurs) == 0 else 'Non conforme',
            'détails': f"{len(erreurs)} erreur(s) détectée(s)"
        }
    }


# ════════════════════════════════════════════════════════════════
# 9. FONCTION PRINCIPALE - AVEC PRIORITÉ ABSOLUE À GEMINI VISION
# ════════════════════════════════════════════════════════════════

def extraire_et_analyser(file_path: str, type_fournisseur: str = None) -> Dict[str, Any]:
    """
    Fonction principale : OCR + phi3 + Gemini Vision directe.
    ⭐ PRIORITÉ ABSOLUE à Gemini Vision pour le fournisseur et les annexes.
    ⭐ type_fournisseur : 'service', 'fourniture', 'Nouveauf'
    """
    
    print("="*60)
    print(f"📄 TRAITEMENT : {file_path}")
    print(f"📋 Type fournisseur : {type_fournisseur}")
    print("="*60)
    
    # ──────────────────────────────────────────────────────────────
    # 1. OCR
    # ──────────────────────────────────────────────────────────────
    print(f"🔍 Étape 1 : OCR - Extraction des critères SOMAS...")
    
    try:
        resultats_ocr = extraire_criteres_somas(file_path, verbose=True)
    except Exception as e:
        print(f"   ❌ Erreur OCR: {e}")
        resultats_ocr = {}
    
    print(f"   ✅ OCR terminé : {resultats_ocr.get('nb_mots_ocr', 0)} mots extraits")
    
    texte_complet = resultats_ocr.get('texte_complet', '')
    if not texte_complet:
        texte_complet = resultats_ocr.get('texte_extrait', '')
    
    print(f"   📝 Taille du texte complet : {len(texte_complet)} caractères")
    
    if not texte_complet or len(texte_complet) < 50:
        return resultat_par_defaut(file_path)
    
    type_objet = resultats_ocr.get('type_objet', 'service')
    objet_ocr = resultats_ocr.get('objet_commande_trouve', 'Non détecté')
    
    taxe_professionnelle_ok = resultats_ocr.get('taxe_professionnelle_ok', False)
    if not taxe_professionnelle_ok:
        if 'TAXE PROFESSIONNELLE' in texte_complet or 'PATENTE' in texte_complet:
            taxe_professionnelle_ok = True

    
    ICE_SOMAS_ATTENDU = "000000695000053"
    
    # ⭐ 1. Utiliser la liste des ICE déjà détectés par l'OCR (ligne 3 de votre log)
    tous_les_ice = resultats_ocr.get('all_ice_detected', [])
    
    # ⭐ 2. Si la liste est vide, on fait une recherche nous-mêmes (fallback)
    if not tous_les_ice:
        ic_pattern = r'ICE\s*[/:.\s]*0?(\d{14,15})'
        tous_les_ice = re.findall(ic_pattern, texte_complet, re.IGNORECASE)
    
    ice_fournisseur = None
    ice_somas_present = False
    
    # ⭐ 3. Parcourir tous les ICE trouvés
    for ice in tous_les_ice:
        # ⭐ CORRECTION ICI : Normaliser les zéros en début de chaîne
        ice_normalise = ice.lstrip('0')
        somas_normalise = ICE_SOMAS_ATTENDU.lstrip('0')
        
        if ice_normalise == somas_normalise:
            ice_somas_present = True
        elif ice_fournisseur is None:
            ice_fournisseur = ice
    
    # ⭐ 4. Mettre à jour les résultats
    if ice_fournisseur:
        resultats_ocr['ice_ok'] = True
        resultats_ocr['ice_valeur'] = ice_fournisseur
    else:
        resultats_ocr['ice_ok'] = False
        resultats_ocr['ice_valeur'] = None
    
    resultats_ocr['ice_somas_present'] = ice_somas_present
    
   # ⭐ 5. Logs cohérents (Ordre corrigé)
    print(f"   🔍 Tous les ICE trouvés : {tous_les_ice}")
    print(f"   🔍 ICE Fournisseur détecté : {ice_fournisseur}")
    print(f"   🔍 ICE SOMAS présent : {ice_somas_present}")
    # ──────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────
    
    # ──────────────────────────────────────────────────────────────
    # ⭐ 2. GEMINI VISION - DÉTECTION COMPLÈTE (objet + fournisseur + annexes + dates annexes + date édition + est_en_regle)
    # ──────────────────────────────────────────────────────────────
    print(f"👁️ Étape 2 : Gemini Vision - Détection complète...")
    
    global _VISION_RESULT
    _VISION_RESULT = extraire_objet_et_annexes_avec_vision_directe(file_path, texte_complet)
    
    # ⭐⭐⭐ Récupérer la date d'édition depuis Vision
    date_edition_vision = None
    if _VISION_RESULT and _VISION_RESULT.get('date_edition'):
        date_edition_vision = _VISION_RESULT.get('date_edition')
        if date_edition_vision and date_edition_vision != "null" and date_edition_vision != "Non détectée":
            print(f"   ✅ Vision - Date d'édition: {date_edition_vision}")
        else:
            print(f"   ⚠️ Vision - Date d'édition: Non détectée")
    else:
        print(f"   ⚠️ Vision - Date d'édition: Non détectée")
    
    # ⭐⭐⭐ Récupérer est_en_regle depuis Vision
    est_en_regle = None
    if _VISION_RESULT and _VISION_RESULT.get('est_en_regle') is not None:
        est_en_regle = _VISION_RESULT.get('est_en_regle')
        if est_en_regle is True:
            print(f"   ✅ Vision - Est en règle (case 'N'a pas' cochée): TRUE")
        elif est_en_regle is False:
            print(f"   ❌ Vision - Est en règle (case 'N'a pas' décochée): FALSE")
        else:
            print(f"   ⚠️ Vision - Est en règle: {est_en_regle}")
    else:
        print(f"   ⚠️ Vision - Est en règle: Non détecté (valeur manquante)")
    
    # ⭐ Récupérer les dates des annexes depuis Vision
    dates_annexes_vision = {}
    if _VISION_RESULT and _VISION_RESULT.get('dates_annexes'):
        dates_annexes_vision = _VISION_RESULT['dates_annexes']
        print(f"   📅 Dates des annexes détectées par Vision:")
        for type_annexe, date_str in dates_annexes_vision.items():
            if date_str and date_str != "null" and date_str != "Non détectée":
                print(f"      ✅ {type_annexe}: {date_str}")
            else:
                print(f"      ⚠️ {type_annexe}: Non détectée")

        # ──────────────────────────────────────────────────────────────
    # ⭐ CORRECTION : FORCER L'OBJET "DÉTECTÉ" SI ENGAGEMENT D'IMPORTATION EST PRÉSENT
    # ──────────────────────────────────────────────────────────────
    # Récupérer les annexes détectées par Vision (booléens)
    annexes_vision = _VISION_RESULT.get('annexes', {}) if _VISION_RESULT else {}
    
    # Si "engagement_importation" est présent, on force l'objet à "Détecté"
    if annexes_vision.get('engagement_importation', False):
        objet_final = "Engagement d'importation (EI)"
        source_objet = 'vision_annexe_force'
        print(f"   ✅ Objet forcé par annexe 'engagement_importation': {objet_final}")
    # ──────────────────────────────────────────────────────────────
    
    # ──────────────────────────────────────────────────────────────
    # ⭐ 3. FOURNISSEUR : PRIORITÉ ABSOLUE À GEMINI VISION
    # ──────────────────────────────────────────────────────────────
    
        # ──────────────────────────────────────────────────────────────
    # ⭐ 3. FOURNISSEUR : UNIQUEMENT GEMINI VISION
    # ──────────────────────────────────────────────────────────────
    print(f"🔍 Étape 3 : Détection du fournisseur...")
    
    fournisseur = "Non détecté"
    source_fournisseur = None
    
    if _VISION_RESULT and not _VISION_RESULT.get('erreur'):
        fournisseur_vision = _VISION_RESULT.get('fournisseur')
        if fournisseur_vision and fournisseur_vision != "null" and fournisseur_vision != "Non détecté":
            fournisseur = fournisseur_vision
            source_fournisseur = 'vision_directe'
            print(f"   ✅ Fournisseur détecté par Vision: {fournisseur}")
        else:
            print(f"   ⚠️ Vision n'a pas détecté de fournisseur")
    
    # ⭐ SUPPRESSION DU FALLBACK OCR (Plus de vérification de liste)
    
    print(f"   🏢 Fournisseur final : {fournisseur} (source: {source_fournisseur})")
    
       # ──────────────────────────────────────────────────────────────
    # ⭐ 4. OBJET DE COMMANDE (PRIORITÉ ABSOLUE À L'ANNEXE)
    # ──────────────────────────────────────────────────────────────
    print(f"🧠 Étape 4 : Détection de l'objet de commande...")
    
    objet_final = "Non détecté"
    source_objet = None

    # 1. ⭐ PRIORITÉ 1 : Forçage par annexe (engagement_importation)
    if _VISION_RESULT and not _VISION_RESULT.get('erreur'):
        annexes_vision = _VISION_RESULT.get('annexes', {})
        if annexes_vision.get('engagement_importation', False):
            objet_final = "Engagement d'importation (EI)"
            source_objet = 'vision_annexe_force'
            print(f"   ✅ Objet forcé par annexe 'engagement_importation': {objet_final}")
    
    # 2. PRIORITÉ 2 : Si pas d'annexe, essayer Vision
    if objet_final == "Non détecté" and _VISION_RESULT and not _VISION_RESULT.get('erreur'):
        objet_vision = _VISION_RESULT.get('objet_commande')
        if objet_vision and objet_vision != "null" and objet_vision != "Non détecté":
            objet_final = objet_vision
            source_objet = 'vision_directe'
            print(f"   ✅ Objet détecté par Vision: {objet_final}")
        else:
            print(f"   ⚠️ Vision n'a pas détecté d'objet")

    # 3. PRIORITÉ 3 : Fallback phi3
    if objet_final == "Non détecté":
        print(f"   🔄 Fallback phi3 pour l'objet...")
        objet_phi3, source_phi3 = _detecter_objet_phi3(texte_complet)
        if objet_phi3 and objet_phi3 != "Non détecté":
            objet_final = objet_phi3
            source_objet = source_phi3
            print(f"   ✅ Objet détecté par phi3: {objet_final}")

    # 4. PRIORITÉ 4 : Fallback regex
    if objet_final == "Non détecté":
        objet_regex, source_regex = _detecter_objet_regex(texte_complet)
        if objet_regex and objet_regex != "Non détecté":
            objet_final = objet_regex
            source_objet = source_regex
            print(f"   ✅ Objet détecté par regex: {objet_final}")

    # 5. PRIORITÉ 5 : Dernier fallback OCR
    if objet_final == "Non détecté":
        objet_final = objet_ocr
        source_objet = 'ocr (fallback)'

    print(f"   📋 Objet final : {objet_final} (source: {source_objet})")
    # ──────────────────────────────────────────────────────────────
    # 5. DÉTECTION DE LA NATURE DE L'OPÉRATION
    # ──────────────────────────────────────────────────────────────
    print(f"🔍 Étape 5 : Détection de la nature de l'opération...")
    nature_operation = detecter_nature_operation(objet_final, texte_complet)
    print(f"   📋 Nature détectée: {nature_operation}")

    # ⭐ CRÉATION DE CONFORMITE (AVANT L'ÉTAPE 5.5)
    conformite = {
        'est_conforme': False,
        'erreurs': [],
        'nb_erreurs': 0,
        'avertissements': []
    }

    # ──────────────────────────────────────────────────────────────
    # ⭐ ÉTAPE 5.5 : PRÉDICTION DES ANNEXES MANQUANTES
    # ──────────────────────────────────────────────────────────────
    print(f"🔍 Étape 5.5 : Prédiction des annexes manquantes...")
    
    from core.checklist_rules import ANNEXES_OBLIGATOIRES_PAR_NATURE
    regles = ANNEXES_OBLIGATOIRES_PAR_NATURE.get(nature_operation, ANNEXES_OBLIGATOIRES_PAR_NATURE["general"])
    
    # ⭐ AJOUT : Si nouveau fournisseur, ajouter attestation_rib aux règles
    if type_fournisseur == 'Nouveauf':
        regles['attestation_rib'] = True
        print(f"   📋 Nouveau fournisseur: Attestation RIB ajoutée aux règles obligatoires")
    
    vision_annexes_detectees = {}
    if _VISION_RESULT and not _VISION_RESULT.get('erreur'):
        vision_annexes_detectees = _VISION_RESULT.get('annexes', {})
    
    elements_manquants_predits = []
    for annexe, obligatoire in regles.items():
        if obligatoire:
            est_presente = vision_annexes_detectees.get(annexe, False)
            if not est_presente:
                message = f"Annexe obligatoire manquante : {annexe.replace('_', ' ').title()}"
                elements_manquants_predits.append(message)
                print(f"   ⚠️ Prédiction : {message}")
    
    if elements_manquants_predits:
        for err in elements_manquants_predits:
            if err not in conformite['erreurs']:
                conformite['erreurs'].append(err)
        conformite['nb_erreurs'] = len(conformite['erreurs'])
    
    print(f"   📋 Annexes manquantes prédites : {len(elements_manquants_predits)}")
    # ──────────────────────────────────────────────────────────────
    
    # ──────────────────────────────────────────────────────────────
    # 6. DOCUMENTS ANNEXES
    # ──────────────────────────────────────────────────────────────
    print(f"📎 Étape 6 : Détection des documents annexes...")
    
    annexes_detectees = detecter_annexes_avec_fallback(texte_complet, file_path, objet_final)

    # ⭐⭐⭐ AJOUT : Filtrer l'attestation RIB ⭐⭐⭐
    annexes_detectees = filtrer_attestation_rib(annexes_detectees, texte_complet, type_fournisseur)
    
    # ⭐ Passer type_fournisseur à enrichir_annexes_avec_nature
    annexes_finales = enrichir_annexes_avec_nature(annexes_detectees, nature_operation, texte_complet, type_fournisseur)
    
    print(f"   📋 Documents annexes finaux:")
    for doc, present in annexes_finales.items():
       print(f"      - {doc}: {'✅' if present else '❌'}")



    
    # ──────────────────────────────────────────────────────────────
    # 7. CONSTRUCTION DU RÉSULTAT
    # ──────────────────────────────────────────────────────────────
    print(f"🔗 Étape 7 : Construction du résultat...")
    
    numero_facture = resultats_ocr.get('numero_facture')
    if _VISION_RESULT and _VISION_RESULT.get('numero_facture'):
        numero_facture = _VISION_RESULT.get('numero_facture')
    
    date_facture = resultats_ocr.get('date_trouvee')
    if _VISION_RESULT and _VISION_RESULT.get('date_facture'):
        date_facture = _VISION_RESULT.get('date_facture')
        print(f"   ✅ Date utilisée (Vision): {date_facture}")
    else:
        print(f"   ⚠️ Date utilisée (OCR): {date_facture}")
    
    montant_ttc = None
    if _VISION_RESULT and _VISION_RESULT.get('montant_ttc'):
        montant_ttc = _VISION_RESULT.get('montant_ttc')
    
    # ⭐⭐⭐ VALIDATION DES DATES AVEC LES DATES DES ANNEXES (DE VISION)
    validation_dates = None
    dates_annexes = {}
    
    if date_facture and dates_annexes_vision:
        # Convertir les dates de Vision en objets datetime
        for type_annexe, date_str in dates_annexes_vision.items():
            if date_str and date_str != "null" and date_str != "Non détectée":
                try:
                    date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                    dates_annexes[type_annexe] = {
                        'date': date_obj,
                        'date_str': date_str,
                        'source': 'vision'
                    }
                except:
                    pass
        
        # ⭐ Utiliser les dates de Vision pour la validation
        if dates_annexes:
            validation_dates = valider_date_facture_avec_annexes_vision(
                date_facture,
                dates_annexes
            )
            
            print(f"   📅 Validation dates (Vision):")
            print(f"      - Date facture: {date_facture}")
            for type_annexe, info in dates_annexes.items():
                print(f"      - Date {type_annexe}: {info['date_str']}")
            print(f"      - Est récente: {'✅' if validation_dates['est_recente'] else '❌'}")
            print(f"      - Valide: {'✅' if validation_dates['valide'] else '❌'}")
            if validation_dates['erreurs']:
                for err in validation_dates['erreurs']:
                    print(f"         ⚠️ ERREUR: {err}")
            if validation_dates['avertissements']:
                for warn in validation_dates['avertissements']:
                    print(f"         ⚠️ {warn}")
        else:
            print(f"   ⚠️ Aucune date d'annexe trouvée par Vision")
    
    # ⭐⭐⭐ DATE D'ÉDITION ET EXPIRATION (UNIQUEMENT DE VISION - PAS D'OCR)
    date_edition = None
    date_expiration = None

    # ⭐ 1. Utiliser UNIQUEMENT la date d'édition de Vision
    if date_edition_vision and date_edition_vision != "null" and date_edition_vision != "Non détectée":
        # ⭐⭐ Essayer plusieurs formats de date
        formats = [
            '%d/%m/%Y',      # 26/03/2026
            '%d-%m-%Y',      # 26-03-2026
            '%d.%m.%Y',      # 26.03.2026
            '%Y/%m/%d',      # 2026/03/26
            '%Y-%m-%d',      # 2026-03-26
            '%d %m %Y',      # 26 03 2026
            '%d/%m/%y',      # 26/03/26
            '%d-%m-%y',      # 26-03-26
            '%d.%m.%y',      # 26.03.26
        ]
        
        for fmt in formats:
            try:
                date_edition = datetime.strptime(date_edition_vision, fmt)
                date_expiration = date_edition + timedelta(days=180)
                print(f"   ✅ Date d'édition (Vision): {date_edition.strftime('%d/%m/%Y')}")
                print(f"   ✅ Date d'expiration: {date_expiration.strftime('%d/%m/%Y')}")
                break
            except ValueError:
                continue
        
        if not date_edition:
            print(f"   ⚠️ Erreur parsing date d'édition Vision: '{date_edition_vision}' - aucun format valide")

    # ⭐ 2. LAISSER LES CHAMPS VIDES SI AUCUNE DATE D'ÉDITION
    # Ne pas utiliser la date facture comme fallback
    if not date_edition:
        date_edition = None
        date_expiration = None
        print(f"   ⚠️ Aucune date d'édition trouvée - case laissée vide")
    
    # ⭐⭐⭐ VÉRIFICATION DE L'ATTESTATION DE RÉGULARITÉ FISCALE
    attestation_fiscale_trouvee = False

    # Vérifier dans les annexes détectées
    for doc_name, present in annexes_finales.items():
        if 'attestation' in doc_name.lower() or 'fiscale' in doc_name.lower():
            attestation_fiscale_trouvee = True
            break

    # Vérifier dans le texte OCR
    if not attestation_fiscale_trouvee and texte_complet:
        if 'attestation' in texte_complet.lower() and ('fiscale' in texte_complet.lower() or 'régularité' in texte_complet.lower()):
            attestation_fiscale_trouvee = True
            print(f"   ✅ Attestation de régularité fiscale détectée dans le texte OCR")
    
    # ⭐⭐⭐ CORRECTION : Construction du résultat avec validation CNSS
    checklist_somas = {
        'date_valide': validation_dates['valide'] and validation_dates['est_recente'] if validation_dates else resultats_ocr.get('date_valide', False),
        'date_trouvee': date_facture,
        'date_edition': date_edition.strftime('%d/%m/%Y') if date_edition else None,
        'date_expiration': date_expiration.strftime('%d/%m/%Y') if date_expiration else None,
        'date_edition_absente': date_edition is None,
        'attestation_fiscale_detectee': attestation_fiscale_trouvee,
        'est_en_regle': est_en_regle,  # ⭐ AJOUTÉ 
        'if_ok': resultats_ocr.get('if_ok', False),
        'ice_ok': resultats_ocr.get('ice_ok', False),
        'ice_valeur': resultats_ocr.get('ice_valeur') if resultats_ocr.get('ice_ok') else None,
        'cnss_ok': resultats_ocr.get('cnss_ok', False),
        'cnss_valeur': resultats_ocr.get('cnss_valeur') if resultats_ocr.get('cnss_ok') else None,
        'rc_ok': resultats_ocr.get('rc_ok', False),
        'rc_valeur': resultats_ocr.get('rc_valeur'),
        'rib_ok': resultats_ocr.get('rib_ok', False),
        'rib_valeur': resultats_ocr.get('rib_valeur'),
        'cachet_ok': resultats_ocr.get('cachet_ok', False),
        'montant_lettres_ok': resultats_ocr.get('montant_lettres_ok', False),
        'objet_commande_ok': resultats_ocr.get('objet_commande_ok', False),
        'objet_commande_trouve': resultats_ocr.get('objet_commande_trouve'),
        'type_objet': resultats_ocr.get('type_objet'),
        'taxe_professionnelle_ok': taxe_professionnelle_ok,
    }
    
    resultat_final = {
        'numéro_facture': numero_facture,
        'date_facture': date_facture,
        'fournisseur': fournisseur,
        'objet_commande': objet_final,
        'montant_ht': None,
        'montant_ttc': montant_ttc,
        'articles': [],
        'annexes_detectees': annexes_finales,
        'nature_operation': nature_operation,
        'validation_dates': validation_dates,
        'dates_annexes': dates_annexes,
        'est_en_regle': est_en_regle,  # ⭐ AJOUTÉ
        'checklist_somas': checklist_somas,
        
        # ⭐⭐⭐ CORRECTION MAJEURE ICI ⭐⭐⭐
        # On passe la variable conformite qui contient les annexes manquantes
        'conformite': conformite,  
        
        # ⭐⭐⭐ AJOUTEZ CETTE LIGNE ICI ⭐⭐⭐
        'all_ice_detected': resultats_ocr.get('all_ice_detected', []),  # Transmet la liste des ICE
        
        '_metadata': {
            'source_file': os.path.basename(file_path),
            'extraction_method': 'Gemini Vision directe + OCR fallback',
            'nb_mots_ocr': resultats_ocr.get('nb_mots_ocr', 0),
            'confiance_moyenne_ocr': resultats_ocr.get('confiance_moyenne', 0),
            'objet_source': source_objet,
            'fournisseur_source': source_fournisseur,
            'nature_operation': nature_operation,
            'annexes_source': 'vision_directe' if any(annexes_finales.values()) else 'phi3',
            'taille_texte_analyse': len(texte_complet),
            'date_extraction': datetime.now().isoformat(),
            'texte_complet': texte_complet
        }
    }
    
    # ──────────────────────────────────────────────────────────────
    # 8. RAPPORT DE CONFORMITÉ
    # ──────────────────────────────────────────────────────────────
    resultat_final['conformite'] = generer_rapport_conformite(resultat_final)
    
    # ⭐⭐⭐ AJOUT : Ajouter les annexes manquantes dans les erreurs du rapport de conformité
    if elements_manquants_predits:
        for err in elements_manquants_predits:
            if err not in resultat_final['conformite']['erreurs']:
                resultat_final['conformite']['erreurs'].append(err)
        resultat_final['conformite']['nb_erreurs'] = len(resultat_final['conformite']['erreurs'])
        resultat_final['conformite']['est_conforme'] = len(resultat_final['conformite']['erreurs']) == 0
        print(f"   ✅ Annexes manquantes ajoutées au rapport de conformité")
    
    print(f"✅ Extraction complète !")
    print("="*60)
    
    return resultat_final


def resultat_par_defaut(file_path: str) -> Dict[str, Any]:
    """Retourne un résultat par défaut en cas d'échec."""
    return {
        'numéro_facture': None,
        'date_facture': None,
        'fournisseur': 'Non détecté',
        'objet_commande': 'Non détecté',
        'montant_ht': None,
        'montant_ttc': None,
        'articles': [],
        'annexes_detectees': {},
        'nature_operation': 'general',
        'validation_dates': None,
        'dates_annexes': {},
        'est_en_regle': None,  # ⭐ AJOUTÉ
        'checklist_somas': {
            'date_edition': None,
            'date_expiration': None,
            'date_edition_absente': True,
            'attestation_fiscale_detectee': False,
            'est_en_regle': None,  # ⭐ AJOUTÉ
        },
        '_metadata': {
            'source_file': os.path.basename(file_path),
            'extraction_method': 'OCR + phi3 + Gemini',
            'erreur': 'Texte OCR vide'
        },
        'conformite': {
            'est_conforme': False,
            'nb_erreurs': 1,
            'nb_avertissements': 0,
            'erreurs': ['Échec de l\'extraction'],
            'avertissements': [],
            'criteres': {
                'champs_obligatoires': 'Non conforme',
                'détails': '1 erreur(s) détectée(s)'
            }
        }
    }


# ════════════════════════════════════════════════════════════════
# 10. DÉTECTION DU FOURNISSEUR PAR OCR
# ════════════════════════════════════════════════════════════════




def extraire_facture(file_path: str, type_fournisseur: str = None) -> Dict[str, Any]:
    """Fonction principale d'extraction."""
    return extraire_et_analyser(file_path, type_fournisseur=type_fournisseur)