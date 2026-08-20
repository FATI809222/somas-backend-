# tests/test_ocr_extraction.py
#
# Teste chaque détecteur regex indépendamment, sur du TEXTE simulé (pas
# d'image, pas d'OCR). Ça permet d'isoler un bug de règle d'un bug d'OCR.
#
# Lancer avec : pytest tests/test_ocr_extraction.py -v

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from ocr_extractor import (
    detecter_ice, detecter_cnss, detecter_rc, detecter_if,
    detecter_montant_lettres, detecter_objet_commande,
    detecter_taxe_professionnelle, estimer_type_objet,
)


# ─── ICE ────────────────────────────────────────────────────────
@pytest.mark.parametrize("texte,attendu_present", [
    ("ICE: 001234567000012", True),
    ("I.C.E N° 001234567000045", True),
    ("LC.E : 001234567000078", True),  # erreur OCR fréquente I -> L
    ("Aucune mention d'identifiant ici", False),
    ("", False),
])
def test_detecter_ice(texte, attendu_present):
    present, valeur = detecter_ice(texte.upper())
    assert present == attendu_present
    if attendu_present:
        assert valeur is not None and len(valeur) >= 14


# ─── MONTANT EN LETTRES : cas de régression du bug substring ────
@pytest.mark.parametrize("texte,attendu", [
    # AVANT correction, ces deux lignes étaient de FAUX POSITIFS car
    # "UN" est une sous-chaîne de "AUCUN" et "COMMUN"
    ("Aucun cachet trouvé sur ce document", False),
    ("Accord commun entre les parties", False),
    ("Facture réglée. Rien d'autre à signaler", False),
    # vrais positifs
    ("Arrêtée la présente facture à la somme de dix mille dirhams", True),
    ("Montant en lettres : cinquante mille dirhams", True),
    ("Somme de : trois cent mille dirhams", True),
])
def test_detecter_montant_lettres_pas_de_faux_positif(texte, attendu):
    assert detecter_montant_lettres(texte.upper()) == attendu


# ─── CNSS / RC / IF / Taxe pro ───────────────────────────────────
def test_detecter_cnss():
    present, valeur = detecter_cnss("CNSS N° 1234567".upper())
    assert present is True
    assert valeur == "1234567"

def test_detecter_cnss_absent():
    present, _ = detecter_cnss("Aucune référence sociale".upper())
    assert present is False

def test_detecter_rc_format_ville():
    present, valeur = detecter_rc("R. C. Casablanca 520985".upper())
    assert present is True
    assert valeur == "520985"

def test_detecter_if():
    assert detecter_if("Identifiant Fiscal : 12345678".upper()) is True
    assert detecter_if("Pas d'identifiant ici".upper()) is False

def test_detecter_taxe_professionnelle():
    assert detecter_taxe_professionnelle("Taxe Professionnelle: 12345678".upper()) is True
    assert detecter_taxe_professionnelle("Rien".upper()) is False


# ─── Objet de commande / classification ──────────────────────────
def test_detecter_objet_commande():
    assert detecter_objet_commande("Objet: Travaux d'installation".upper()) is True
    assert detecter_objet_commande("Rien de spécifique ici".upper()) is False

@pytest.mark.parametrize("texte,type_attendu", [
    ("Location véhicule pour le mois", "location"),
    ("Travaux d'installation électrique", "travaux"),
    ("Formation du personnel technique", "formation"),
    ("Fourniture de matériel informatique", "fourniture"),
    ("Prestation de transit et quittance douane", "transitaire"),
    ("Contrôle réglementaire des installations", "controle"),
    ("Texte générique sans mot-clé", "service"),
])
def test_estimer_type_objet(texte, type_attendu):
    assert estimer_type_objet(texte.upper()) == type_attendu