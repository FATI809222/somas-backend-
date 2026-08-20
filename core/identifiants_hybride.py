# backend/identifiants_hybride.py
"""
identifiants_hybride.py

Principe : phi3 localise la valeur candidate d'un identifiant dans le texte
OCR (il absorbe la variation infinie de formulation selon les fournisseurs :
"ICE", "I.C.E N°", "Identifiant Commun...", erreurs OCR type "LC.E"...).

Une regex de FORMAT (une seule par type de champ, valable pour tous les
fournisseurs car fixée par la réglementation, pas par l'entreprise) valide
ensuite ce que phi3 a trouvé.
"""

import json
import re
import ollama
from typing import Optional, Dict, Any

MODEL_NAME = "phi3:3.8b-instruct"


# ─────────────────────────────────────────────────────────────────
# 1. VALIDATION DE FORMAT
# ─────────────────────────────────────────────────────────────────

def _nettoyer_chiffres(valeur: Optional[str]) -> str:
    """Ne garde que les chiffres d'une valeur candidate."""
    if not valeur:
        return ""
    return re.sub(r"\D", "", str(valeur))


def valider_ice(valeur: Optional[str]) -> bool:
    """ICE marocain : toujours 15 chiffres."""
    return len(_nettoyer_chiffres(valeur)) == 15


def valider_rib(valeur: Optional[str]) -> bool:
    """RIB marocain : toujours 24 chiffres."""
    return len(_nettoyer_chiffres(valeur)) == 24


def valider_cnss(valeur: Optional[str]) -> bool:
    """N° CNSS : généralement 6 à 8 chiffres."""
    n = len(_nettoyer_chiffres(valeur))
    return 6 <= n <= 8


def valider_rc(valeur: Optional[str]) -> bool:
    """Registre de commerce : suite de chiffres, au moins 4."""
    return len(_nettoyer_chiffres(valeur)) >= 4


def valider_if(valeur: Optional[str]) -> bool:
    """Identifiant fiscal : au moins 6 chiffres."""
    return len(_nettoyer_chiffres(valeur)) >= 6


def valider_taxe_professionnelle(valeur: Optional[str]) -> bool:
    """Taxe professionnelle / patente : au moins 6 chiffres."""
    return len(_nettoyer_chiffres(valeur)) >= 6


VALIDATEURS = {
    "ice": valider_ice,
    "rib": valider_rib,
    "cnss": valider_cnss,
    "rc": valider_rc,
    "if": valider_if,
    "taxe_professionnelle": valider_taxe_professionnelle,
}


# ─────────────────────────────────────────────────────────────────
# 2. LOCALISATION PAR phi3
# ─────────────────────────────────────────────────────────────────

_PROMPT_LOCALISATION = """Tu es un extracteur d'identifiants sur des factures marocaines.
Voici le texte OCR d'une facture (peut contenir des erreurs de reconnaissance) :

{texte}

Cherche dans ce texte les identifiants suivants, même s'ils sont mal orthographiés
à cause de l'OCR (ex: "LC.E" ou "l.C.E" pour ICE, "R C" pour RC...) :
- ice : Identifiant Commun de l'Entreprise (15 chiffres)
- rib : Relevé d'Identité Bancaire (24 chiffres)
- cnss : numéro CNSS (6 à 8 chiffres)
- rc : numéro de Registre de Commerce
- if : Identifiant Fiscal
- taxe_professionnelle : numéro de taxe professionnelle / patente

Renvoie UNIQUEMENT un objet JSON avec ces 6 clés. Pour chaque champ, mets la suite
de chiffres trouvée (sans espaces ni points), ou null si tu ne trouves rien.
Ne devine jamais un chiffre que tu ne vois pas dans le texte.
"""


def localiser_identifiants_phi3(texte_complet: str) -> Dict[str, Optional[str]]:
    """
    Demande à phi3 de localiser les identifiants dans le texte OCR.
    """
    resultat_vide = {cle: None for cle in VALIDATEURS}

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": _PROMPT_LOCALISATION.format(texte=texte_complet)}],
            options={"temperature": 0.0, "num_predict": 512},
        )
        content = response["message"]["content"]

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

        candidats = json.loads(json_str)
        return {cle: candidats.get(cle) for cle in VALIDATEURS}

    except Exception as e:
        print(f"   ⚠️ phi3 localisation identifiants a échoué : {e}")
        return resultat_vide


# ─────────────────────────────────────────────────────────────────
# 3. RÉCONCILIATION
# ─────────────────────────────────────────────────────────────────

def reconcilier_champ(
    cle: str,
    valeur_regex: Optional[str],
    ok_regex: bool,
    valeur_phi3: Optional[str],
) -> Dict[str, Any]:
    """
    Combine la détection regex existante et le candidat phi3.
    """
    valider = VALIDATEURS[cle]
    regex_ok = ok_regex and valeur_regex and valider(valeur_regex)
    phi3_ok = valeur_phi3 and valider(valeur_phi3)

    if regex_ok:
        if phi3_ok and _nettoyer_chiffres(valeur_phi3) != _nettoyer_chiffres(valeur_regex):
            return {
                "valeur": valeur_regex,
                "statut": "a_verifier",
                "source": "desaccord_regex_phi3",
                "valeur_alternative_phi3": valeur_phi3,
            }
        return {"valeur": valeur_regex, "statut": "conforme", "source": "regex"}

    if phi3_ok:
        return {"valeur": valeur_phi3, "statut": "conforme", "source": "phi3"}

    valeur_douteuse = valeur_regex or valeur_phi3
    if valeur_douteuse:
        return {"valeur": valeur_douteuse, "statut": "a_verifier", "source": "format_invalide"}

    return {"valeur": None, "statut": "non_detecte", "source": None}


def enrichir_checklist_avec_phi3(texte_complet: str, resultats_ocr: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Fonction principale à appeler depuis extractor.py
    """
    candidats_phi3 = localiser_identifiants_phi3(texte_complet)

    mapping_regex = {
        "ice": ("ice_valeur", "ice_ok"),
        "rib": ("rib_valeur", "rib_ok"),
        "cnss": ("cnss_valeur", "cnss_ok"),
        "rc": ("rc_valeur", "rc_ok"),
        "if": (None, "if_ok"),
        "taxe_professionnelle": (None, "taxe_professionnelle_ok"),
    }

    resultat = {}
    for cle, (cle_valeur, cle_ok) in mapping_regex.items():
        valeur_regex = resultats_ocr.get(cle_valeur) if cle_valeur else None
        ok_regex = resultats_ocr.get(cle_ok, False)
        resultat[cle] = reconcilier_champ(cle, valeur_regex, ok_regex, candidats_phi3.get(cle))

    return resultat


if __name__ == "__main__":
    # Test
    exemple_texte = "FACTURE ICE : 001234567000089 RC CASABLANCA N° 12345 CNSS: 156.9427"
    from ocr_extractor import detecter_ice, detecter_rc, detecter_cnss

    ice_ok, ice_valeur = detecter_ice(exemple_texte)
    rc_ok, rc_valeur = detecter_rc(exemple_texte)
    cnss_ok, cnss_valeur = detecter_cnss(exemple_texte)

    resultats_ocr_exemple = {
        "ice_valeur": ice_valeur, "ice_ok": ice_ok,
        "rc_valeur": rc_valeur, "rc_ok": rc_ok,
        "cnss_valeur": cnss_valeur, "cnss_ok": cnss_ok,
        "rib_valeur": None, "rib_ok": False,
        "if_ok": False,
        "taxe_professionnelle_ok": False,
    }

    print(json.dumps(enrichir_checklist_avec_phi3(exemple_texte, resultats_ocr_exemple), indent=2, ensure_ascii=False))