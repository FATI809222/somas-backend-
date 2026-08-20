# checklist_config.py
#
# Référentiel de règles SOMAS. C'est LA source de vérité unique pour :
#   - la liste des champs universels obligatoires (socle commun)
#   - la liste des documents annexes requis selon l'objet de la commande
#   - la liste des documents requis selon les conditions contractuelles
#   - la classification des documents annexes (patterns de reconnaissance)
#
# Aucun autre fichier ne doit redéfinir ces listes en dur (c'était le bug
# principal de l'ancien main.py : il dupliquait sa propre logique au lieu
# d'utiliser ce référentiel, ce qui faisait diverger les résultats).

import re
from typing import Optional, Set, List, Dict

# ═══════════════════════════════════════════════════════════════
# SOCLE COMMUN : toujours vérifié, quel que soit l'objet de la facture
# ═══════════════════════════════════════════════════════════════

SOCLE_COMMUN = [
    "date_facture_recente",
    "identifiant_fiscal",
    "ice_fournisseur",
    "taxe_professionnelle",
    "n_cnss",
    "n_registre_commerce",
    "cachet_signature",
    "montant_en_lettres",
    "reference_commande",
    "objet_commande_present",
    "montant_facture_coherent",
    "rib_coordonnees_bancaires",
]

# ═══════════════════════════════════════════════════════════════
# AXE 1 : documents requis selon le type d'objet
# Basé sur le tableau envoyé
# ═══════════════════════════════════════════════════════════════

DOCUMENTS_PAR_OBJET = {
    # Fourniture / achat de biens
    "fourniture": ["bon_livraison_signe_cachete"],
    
    # Service (générique)
    "service": ["pv_reception_ou_attachement_signe_cachete"],
    
    # Travaux
    "travaux": ["pv_reception_ou_attachement_signe_cachete"],
    
    # Études
    "etude": ["validation_bureau_etudes_controle"],
    
    # Location
    "location": ["pv_location_signe_cachete"],
    
    # Formation
    "formation": ["feuille_presence"],
    
    # Mesures / étalonnage
    "mesure_etalonnage": ["certificat_ou_rapport"],
    
    # Contrôle (prestation technique)
    "controle": ["validation_bureau_etudes_controle"],
    
    # Prestation technique (BE, contrôle)
    "prestation_technique": ["validation_bureau_etudes_controle"],
    
    # Import / transitaire
    "importation": ["engagement_importation", "quittance_douane"],
    "transitaire": ["engagement_importation", "quittance_douane"],
}

# ═══════════════════════════════════════════════════════════════
# ALIAS : si estimer_type_objet() renvoie un nom différent
# ═══════════════════════════════════════════════════════════════

ALIAS_TYPE_OBJET = {
    # Mapper les types détectés par l'OCR vers les types du tableau
    "prestation_technique": "prestation_technique",
    "prestation": "prestation_technique",
    "controle": "prestation_technique",
    "etude": "prestation_technique",
    "service": "service",
    # Pour compatibilité avec l'OCR
    "fourniture": "fourniture",
    "travaux": "travaux",
    "location": "location",
    "formation": "formation",
    "mesure_etalonnage": "mesure_etalonnage",
    "transitaire": "transitaire",
    "importation": "transitaire",
}


def resoudre_type_objet(type_objet: str) -> str:
    """Retourne la clé canonique à utiliser dans DOCUMENTS_PAR_OBJET."""
    return ALIAS_TYPE_OBJET.get(type_objet, type_objet)


# ═══════════════════════════════════════════════════════════════
# AXE 2 : documents requis selon les conditions contractuelles
# Basé sur le tableau envoyé
# ═══════════════════════════════════════════════════════════════

def documents_conditions_contractuelles(
    nouveau_fournisseur: bool, 
    a_acompte: bool, 
    a_retenue_garantie: bool
) -> List[str]:
    """
    Retourne les documents requis selon les conditions contractuelles.
    Basé sur le tableau :
    - Nouveau fournisseur (1ère commande) → Attestation RIB
    - Paiement avec caution → Caution/acompte (même banque) ou Caution retenue de garantie
    """
    docs = []
    
    # Nouveau fournisseur (1ère commande)
    if nouveau_fournisseur:
        docs.append("attestation_rib")
    
    # Paiement avec caution - retenue de garantie
    if a_retenue_garantie:
        docs.append("caution_retenue_garantie")
    
    # Paiement avec caution - acompte
    if a_acompte:
        docs.append("caution_acompte_meme_banque")
    
    return docs


def liste_documents_requis(
    type_objet: str,
    nouveau_fournisseur: bool = False,
    a_acompte: bool = False,
    a_retenue_garantie: bool = False,
) -> Set[str]:
    """Version autonome de la combinaison axe 1 + axe 2."""
    type_resolu = resoudre_type_objet(type_objet)
    if type_resolu not in DOCUMENTS_PAR_OBJET:
        raise ValueError(
            f"type_objet inconnu : '{type_objet}'. "
            f"Ajoutez-le dans DOCUMENTS_PAR_OBJET ou ALIAS_TYPE_OBJET."
        )
    requis = set(DOCUMENTS_PAR_OBJET[type_resolu])
    requis.update(documents_conditions_contractuelles(
        nouveau_fournisseur, a_acompte, a_retenue_garantie
    ))
    return requis


# ═══════════════════════════════════════════════════════════════
# CLASSIFICATION DES DOCUMENTS ANNEXES (patterns de reconnaissance)
# Basé sur les types de documents du tableau
# ═══════════════════════════════════════════════════════════════

DOCUMENT_TYPE_KEYWORDS: Dict[str, List[str]] = {
    # Bon de livraison signé et cacheté (Fourniture)
    "bon_livraison_signe_cachete": [
        r'BON\s*DE\s*LIVRAISON',
        r'\bBL\s*N[°O]',
        r'BON\s*DE\s*LIVRAISON\s*N[°O]',
    ],
    
    # PV de réception ou attachement (Travaux)
    "pv_reception_ou_attachement_signe_cachete": [
        r'PROC[ÈE]S[\s-]?VERBAL\s*DE\s*R[ÉE]CEPTION',
        r'\bPV\s*DE\s*R[ÉE]CEPTION',
        r'ATTACHEMENT\s*DES\s*TRAVAUX',
        r'PV\s*DE\s*R[ÉE]CEPTION',
        r'ATTACHEMENT',
    ],
    
    # PV de location signé et cacheté (Location)
    "pv_location_signe_cachete": [
        r'PV\s*DE\s*LOCATION',
        r'PROC[ÈE]S[\s-]?VERBAL\s*DE\s*LOCATION',
        r'CONTRAT\s*DE\s*LOCATION',
        r'LOCATION\s*DE\s*VEHICULE',
    ],
    
    # Validation bureau d'études / bureau de contrôle (Prestation technique)
    "validation_bureau_etudes_controle": [
        r'BUREAU\s*D[\'\s]?[ÉE]TUDES?',
        r'BUREAU\s*DE\s*CONTR[ÔO]LE',
        r'VALIDATION\s*TECHNIQUE',
        r'NOTE\s*DE\s*CALCUL',
        r'CERTIFICAT\s*DE\s*CONFORMIT[ÉE]',
        r'RAPPORT\s*DE\s*CONTR[ÔO]LE',
        r'AVIS\s*TECHNIQUE',
    ],
    
    # Feuille de présence (Formation)
    "feuille_presence": [
        r'FEUILLE\s*DE\s*PR[ÉE]SENCE',
        r'LISTE\s*DE\s*PR[ÉE]SENCE',
        r'EMARGEMENT',
        r'PR[ÉE]SENCE\s*FORMATION',
    ],
    
    # Certificat ou rapport (Mesures / étalonnage)
    "certificat_ou_rapport": [
        r'CERTIFICAT',
        r'RAPPORT\s*DE\s*(MESURE|[ÉE]TALONNAGE)',
        r'CERTIFICAT\s*DE\s*[ÉE]TALONNAGE',
        r'RAPPORT\s*DE\s*MESURE',
        r'PROC[ÈE]S\s*VERBAL\s*DE\s*[ÉE]TALONNAGE',
    ],
    
    # Engagement d'importation (Transitaire)
    "engagement_importation": [
        r'ENGAGEMENT\s*D[\'\s]?IMPORTATION',
        r'ENGAGEMENT\s*D\'IMPORTATION',
        r'DECLARATION\s*D\'IMPORTATION',
    ],
    
    # Quittance douane (Transitaire)
    "quittance_douane": [
        r'QUITTANCE\s*(DE\s*)?DOUANE',
        r'QUITTANCE\s*DOUANE',
        r'FICHE\s*DE\s*LIQUIDATION\s*DOUANE',
        r'BORDEREAU\s*DOUANIER',
    ],
    
    # Attestation RIB (Nouveau fournisseur)
    "attestation_rib": [
        r'ATTESTATION\s*(DE\s*|BANCAIRE\s*)?RIB',
        r'ATTESTATION\s*BANCAIRE',
        r'RELEV[ÉE]\s*D\'IDENTIT[ÉE]\s*BANCAIRE',
        r'RIB\s*ATTESTATION',
    ],
    
    # Caution / acompte (même banque)
    "caution_acompte_meme_banque": [
        r'CAUTION\s*D[\'\s]?ACOMPTE',
        r'ACOMPTE\s*CAUTION',
        r'CAUTION\s*ACOMPTE',
    ],
    
    # Caution retenue de garantie
    "caution_retenue_garantie": [
        r'CAUTION\s*(DE\s*)?RETENUE\s*(DE\s*)?GARANTIE',
        r'RETENUE\s*DE\s*GARANTIE',
        r'GARANTIE\s*DE\s*CAUTION',
    ],
}


def classifier_type_document(texte: str) -> Optional[str]:
    """
    Retourne la clé du type de document reconnu, ou None.
    `texte` doit déjà être en MAJUSCULES.
    """
    for type_doc, patterns in DOCUMENT_TYPE_KEYWORDS.items():
        if any(re.search(p, texte) for p in patterns):
            return type_doc
    return None


# ═══════════════════════════════════════════════════════════════
# FONCTION DE VÉRIFICATION : documents requis vs documents fournis
# ═══════════════════════════════════════════════════════════════

def verifier_documents_requis(
    type_objet: str,
    documents_fournis: Set[str],
    nouveau_fournisseur: bool = False,
    a_acompte: bool = False,
    a_retenue_garantie: bool = False,
) -> dict:
    """
    Vérifie si les documents fournis couvrent bien les documents requis.
    
    Args:
        type_objet: Type d'objet de la commande (ex: 'travaux', 'location')
        documents_fournis: Ensemble des types de documents fournis
        nouveau_fournisseur: Booléen indiquant si c'est un nouveau fournisseur
        a_acompte: Booléen indiquant s'il y a un acompte
        a_retenue_garantie: Booléen indiquant s'il y a une retenue de garantie
    
    Returns:
        Dict avec les documents requis, manquants et présents
    """
    requis = liste_documents_requis(
        type_objet,
        nouveau_fournisseur,
        a_acompte,
        a_retenue_garantie
    )
    
    presents = requis & documents_fournis
    manquants = requis - documents_fournis
    
    return {
        "requis": list(requis),
        "presents": list(presents),
        "manquants": list(manquants),
        "tous_presents": len(manquants) == 0,
    }