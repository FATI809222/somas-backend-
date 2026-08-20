# moteur_regles.py
#
# Moteur de règles déterministe : conformité stricte, comme spécifié au
# départ ("TOUTES les conditions doivent être satisfaites"). Pas de score
# pondéré avec seuil à 70% -- cette logique-là existait dans l'ancien
# main.py et contredisait la spec métier initiale. Supprimée.

from dataclasses import dataclass, field
from checklist_config import (
    SOCLE_COMMUN,
    DOCUMENTS_PAR_OBJET,
    documents_conditions_contractuelles,
    resoudre_type_objet,
)


@dataclass
class Commande:
    reference: str
    type_objet: str
    a_acompte: bool = False
    a_retenue_garantie: bool = False


@dataclass
class Fournisseur:
    ice: str
    nom: str
    nouveau_fournisseur: bool = False


@dataclass
class Facture:
    id: str
    fournisseur: Fournisseur
    commande: Commande
    champs_extraits: dict = field(default_factory=dict)
    documents_fournis: set = field(default_factory=set)


def determiner_documents_requis(facture: Facture) -> set:
    """Combine axe 1 (nature de l'objet) et axe 2 (conditions
    contractuelles) pour obtenir la liste complète des documents attendus."""
    requis = set()

    type_objet = resoudre_type_objet(facture.commande.type_objet)
    if type_objet in DOCUMENTS_PAR_OBJET:
        requis.update(DOCUMENTS_PAR_OBJET[type_objet])
    else:
        # Ne doit normalement jamais arriver si checklist_config est à jour.
        # On le signale explicitement plutôt que de laisser passer une
        # facture sans aucune exigence de document annexe.
        raise ValueError(
            f"type_objet inconnu : '{facture.commande.type_objet}'. "
            f"Ajoutez-le dans DOCUMENTS_PAR_OBJET ou ALIAS_TYPE_OBJET "
            f"(checklist_config.py)."
        )

    requis.update(documents_conditions_contractuelles(
        nouveau_fournisseur=facture.fournisseur.nouveau_fournisseur,
        a_acompte=facture.commande.a_acompte,
        a_retenue_garantie=facture.commande.a_retenue_garantie,
    ))

    return requis


def evaluer_conformite(facture: Facture) -> dict:
    """Retourne un rapport détaillé. Conformité STRICTE : conforme=True
    seulement si absolument tous les items (socle + documents requis)
    sont présents. C'est le SEUL endroit du projet où ce calcul doit
    avoir lieu -- ne pas le reproduire ailleurs (ex: dans main.py)."""
    resultat = {
        "facture_id": facture.id,
        "items_socle": {},
        "documents_requis": {},
        "score": 0.0,
        "conforme": False,
        "elements_manquants": [],
    }

    for item in SOCLE_COMMUN:
        present = bool(facture.champs_extraits.get(item, False))
        resultat["items_socle"][item] = present
        if not present:
            resultat["elements_manquants"].append(item)

    documents_requis = determiner_documents_requis(facture)
    for doc in documents_requis:
        fourni = doc in facture.documents_fournis
        resultat["documents_requis"][doc] = fourni
        if not fourni:
            resultat["elements_manquants"].append(doc)

    total_items = len(SOCLE_COMMUN) + len(documents_requis)
    items_ok = sum(resultat["items_socle"].values()) + sum(resultat["documents_requis"].values())
    resultat["score"] = round(items_ok / total_items, 2) if total_items > 0 else 0.0

    # Conformité stricte : rien ne doit manquer.
    resultat["conforme"] = len(resultat["elements_manquants"]) == 0

    return resultat