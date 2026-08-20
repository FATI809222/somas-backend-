# tests/test_moteur_regles.py
#
# Teste evaluer_conformite() directement, avec des objets Facture
# construits à la main (aucun OCR). Ça valide la LOGIQUE METIER
# indépendamment de la qualité d'extraction.
#
# Lancer avec : pytest tests/test_moteur_regles.py -v

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from moteur_regles import Facture, Fournisseur, Commande, evaluer_conformite
from checklist_config import SOCLE_COMMUN


def facture_complete(type_objet="fourniture", **kwargs):
    """Fabrique une facture avec TOUT le socle commun présent, pour ne
    tester que la logique liée aux documents annexes."""
    return Facture(
        id="test",
        fournisseur=Fournisseur(ice="123", nom="Test", nouveau_fournisseur=False),
        commande=Commande(reference="BC1", type_objet=type_objet),
        champs_extraits={k: True for k in SOCLE_COMMUN},
        documents_fournis=set(),
        **kwargs,
    )


def test_facture_parfaite_est_conforme():
    f = facture_complete(type_objet="fourniture")
    f.documents_fournis = {"bon_livraison_signe_cachete"}
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is True
    assert resultat["elements_manquants"] == []


def test_socle_incomplet_rend_non_conforme():
    f = facture_complete(type_objet="fourniture")
    f.documents_fournis = {"bon_livraison_signe_cachete"}
    f.champs_extraits["ice_fournisseur"] = False  # un seul champ manquant
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is False
    assert "ice_fournisseur" in resultat["elements_manquants"]


@pytest.mark.parametrize("type_objet,doc_attendu", [
    ("fourniture", "bon_livraison_signe_cachete"),
    ("location", "pv_location_signe_cachete"),
    ("formation", "feuille_presence"),
    ("mesure_etalonnage", "certificat_ou_rapport"),
])
def test_document_requis_par_objet_manquant(type_objet, doc_attendu):
    f = facture_complete(type_objet=type_objet)
    f.documents_fournis = set()  # aucun document fourni
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is False
    assert doc_attendu in resultat["elements_manquants"]


def test_travaux_exige_deux_documents():
    f = facture_complete(type_objet="travaux")
    f.documents_fournis = {"pv_reception_ou_attachement_signe_cachete"}  # 1 sur 2
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is False
    assert "validation_bureau_etudes_controle" in resultat["elements_manquants"]


def test_transitaire_exige_deux_documents_douane():
    f = facture_complete(type_objet="transitaire")
    f.documents_fournis = {"engagement_importation"}  # manque quittance douane
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is False
    assert "quittance_douane" in resultat["elements_manquants"]


def test_nouveau_fournisseur_exige_attestation_rib():
    f = facture_complete(type_objet="fourniture")
    f.fournisseur.nouveau_fournisseur = True
    f.documents_fournis = {"bon_livraison_signe_cachete"}  # attestation RIB absente
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is False
    assert "attestation_rib" in resultat["elements_manquants"]

    f.documents_fournis.add("attestation_rib")
    resultat2 = evaluer_conformite(f)
    assert resultat2["conforme"] is True


def test_acompte_et_garantie_cumulables():
    f = facture_complete(type_objet="fourniture", )
    f.commande.a_acompte = True
    f.commande.a_retenue_garantie = True
    f.documents_fournis = {"bon_livraison_signe_cachete"}
    resultat = evaluer_conformite(f)
    assert resultat["conforme"] is False
    assert "caution_acompte_meme_banque" in resultat["elements_manquants"]
    assert "caution_retenue_garantie" in resultat["elements_manquants"]

    f.documents_fournis |= {"caution_acompte_meme_banque", "caution_retenue_garantie"}
    resultat2 = evaluer_conformite(f)
    assert resultat2["conforme"] is True


def test_type_objet_inconnu_leve_une_erreur_explicite():
    f = facture_complete(type_objet="objet_qui_nexiste_pas")
    with pytest.raises(ValueError):
        evaluer_conformite(f)