# main.py - VERSION CORRIGÉE
#
# Changement principal : ce fichier ne contient plus AUCUNE logique de
# conformité. Il se contente de :
#   1. appeler l'extraction OCR (ocr_extractor)
#   2. construire un objet Facture
#   3. déléguer le verdict à moteur_regles.evaluer_conformite()
#
# L'ancienne version recodait un système de score pondéré avec seuil à
# 70% en parallèle du moteur de règles -- les deux pouvaient donner des
# verdicts différents sur la même facture. Supprimé.

import os
import json
from pathlib import Path

from ocr_extractor import extraire_criteres_somas
from moteur_regles import Facture, Fournisseur, Commande, evaluer_conformite

# Ces informations contractuelles ne sont PAS dans l'image de la facture :
# à terme, nouveau_fournisseur doit venir d'une vérification automatique
# (l'ICE extrait existe-t-il déjà dans la base fournisseurs ?) plutôt que
# d'être saisi en dur ici.
NOUVEAU_FOURNISSEUR_DEFAUT = False
A_ACOMPTE_DEFAUT = False
A_RETENUE_GARANTIE_DEFAUT = False


def mapper_criteres_vers_champs_extraits(criteres: dict) -> dict:
    """Convertit la sortie de extraire_criteres_somas() vers les clés
    attendues par SOCLE_COMMUN (checklist_config.py). Un seul endroit
    fait ce mapping -- avant, ce mapping partiel n'existait que pour
    certains champs et les autres (taxe_professionnelle, rib, montant
    facture cohérent...) étaient tout simplement ignorés du verdict final."""
    return {
        "date_facture_recente": criteres["date_valide"],
        "identifiant_fiscal": criteres["if_ok"],
        "ice_fournisseur": criteres["ice_ok"],
        "taxe_professionnelle": criteres["taxe_professionnelle_ok"],
        "n_cnss": criteres["cnss_ok"],
        "n_registre_commerce": criteres["rc_ok"],
        "cachet_signature": criteres["cachet_ok"],
        "montant_en_lettres": criteres["montant_lettres_ok"],
        "reference_commande": criteres["objet_commande_ok"],
        "objet_commande_present": criteres["objet_commande_ok"],
        # Ces deux-là ne sont pas détectables par OCR seul avec fiabilité
        # (nécessitent une comparaison avec le bon de commande/contrat) :
        # à brancher plus tard sur une vraie vérification, pas laisser
        # à True en dur -- ici on les laisse explicitement à False tant
        # que ce sous-système n'existe pas, pour ne jamais donner un faux
        # "conforme".
        "montant_facture_coherent": criteres.get("montant_facture_coherent", False),
        "rib_coordonnees_bancaires": criteres["rib_ok"],
    }


def analyser_facture(
    chemin_facture: str,
    nouveau_fournisseur: bool = NOUVEAU_FOURNISSEUR_DEFAUT,
    a_acompte: bool = A_ACOMPTE_DEFAUT,
    a_retenue_garantie: bool = A_RETENUE_GARANTIE_DEFAUT,
    documents_fournis: set | None = None,
    verbose: bool = True,
) -> dict:
    """Analyse complète d'une facture : extraction OCR + verdict de
    conformité via le moteur de règles unique. Retourne un dict prêt à
    être sérialisé en JSON (donc prêt pour une API / un frontend)."""
    if verbose:
        print(f"Extraction OCR : {chemin_facture}")

    criteres = extraire_criteres_somas(chemin_facture, verbose=verbose)

    champs_extraits = mapper_criteres_vers_champs_extraits(criteres)

    facture = Facture(
        id=os.path.basename(chemin_facture),
        fournisseur=Fournisseur(
            ice=criteres.get("ice_valeur") or "INCONNU",
            nom="À compléter",
            nouveau_fournisseur=nouveau_fournisseur,
        ),
        commande=Commande(
            reference="À compléter",
            type_objet=criteres["type_objet"],
            a_acompte=a_acompte,
            a_retenue_garantie=a_retenue_garantie,
        ),
        champs_extraits=champs_extraits,
        documents_fournis=documents_fournis or set(),
    )

    rapport = evaluer_conformite(facture)

    # on enrichit le rapport avec les infos utiles pour l'affichage
    rapport["valeurs_extraites"] = {
        "ice": criteres.get("ice_valeur"),
        "cnss": criteres.get("cnss_valeur"),
        "rc": criteres.get("rc_valeur"),
        "rib": criteres.get("rib_valeur"),
        "date_facture": criteres.get("date_trouvee"),
        "type_objet_estime": criteres["type_objet"],
    }
    rapport["diagnostics_ocr"] = {
        "nb_mots_ocr": criteres["nb_mots_ocr"],
        "confiance_moyenne": criteres["confiance_moyenne"],
    }

    if verbose:
        statut = "CONFORME" if rapport["conforme"] else "NON CONFORME"
        print(f"Résultat : {statut} (score {rapport['score']*100:.0f}%)")
        if rapport["elements_manquants"]:
            print("Éléments manquants :")
            for e in rapport["elements_manquants"]:
                print(f"  - {e}")

    return rapport


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage : python main.py chemin/vers/facture.pdf [--nouveau-fournisseur]")
        sys.exit(1)

    chemin = sys.argv[1]
    nouveau = "--nouveau-fournisseur" in sys.argv

    rapport = analyser_facture(chemin, nouveau_fournisseur=nouveau)

    with open("rapport_analyse.json", "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)
    print("\nRapport sauvegardé dans rapport_analyse.json")