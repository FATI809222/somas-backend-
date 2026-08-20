# core/checklist_rules.py
"""
Définit les annexes obligatoires selon la nature de l'opération.
Utilisé pour prédire les documents manquants dans le rapport de conformité.
"""

# ⭐ RÈGLES : Quelles annexes sont OBLIGATOIRES pour chaque type d'opération ?
ANNEXES_OBLIGATOIRES_PAR_NATURE = {
    "acquisition": {
        "bon_livraison": True,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False,
        "validation_bureau_etudes_controle": False,
    },
    "prestation_assistance": {
        "bon_livraison": False,
        "pv_reception": True,  # Prestation = PV de réception obligatoire
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False,
        "validation_bureau_etudes_controle": False,
    },
    "etude": {
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": True,  # Étude = Rapport/Certificat obligatoire
        "engagement_importation": False,
        "quittance_douane": False,
        "validation_bureau_etudes_controle": False,
    },
    "location": {
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": True,  # Location = PV de location obligatoire
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False,
        "validation_bureau_etudes_controle": False,
    },
    "formation": {
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": True,  # Formation = Feuille de présence obligatoire
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False,
        "validation_bureau_etudes_controle": False,
    },
    "general": {
        "bon_livraison": False,
        "pv_reception": False,
        "pv_location": False,
        "feuille_presence": False,
        "certificats_rapport": False,
        "engagement_importation": False,
        "quittance_douane": False,
        "validation_bureau_etudes_controle": False,
    }
}