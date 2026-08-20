# tests/test_facture_reelle.py
"""
Test sur une facture réelle : vérifie que le système détecte l'objet de la commande
et les documents requis associés.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# ✅ AJOUTER LE CHEMIN RACINE POUR LES IMPORTS
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parents[1]  # Remonte de tests/ vers Stage SOMAS/
sys.path.insert(0, str(BASE_DIR))              # Pour importer depuis la racine

# Maintenant l'import fonctionne
from ocr_extractor import extraire_criteres_somas
from checklist_config import verifier_documents_requis, liste_documents_requis

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

FACTURES_DIR = BASE_DIR / "factures"
OUTPUT_DIR = BASE_DIR / "outputs" / "test_documents"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# ANALYSE MANUELLE DES FACTURES (VÉRITÉ TERRAIN)
# ═══════════════════════════════════════════════════════════════

VERITE_TERRAIN = {
    "FAC ZIRAOUI CAR.pdf": {
        "type_objet_attendu": "location",
        "documents_fournis": {"pv_location_signe_cachete"},
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture de location de véhicule"
    },
    "FACT.pdf": {
        "type_objet_attendu": "travaux",
        "documents_fournis": {"pv_reception_ou_attachement_signe_cachete"},
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture de travaux - EFFICIENCE MANUFACTURING"
    },
    "FAC3.pdf": {
        "type_objet_attendu": "controle",
        "documents_fournis": {"certificat_ou_rapport"},
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture de contrôle - APAVE MAROC"
    },
    "FAC4.pdf": {
        "type_objet_attendu": "etude",
        "documents_fournis": {
            "pv_reception_ou_attachement_signe_cachete",
            "validation_bureau_etudes_controle"
        },
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture d'étude - SMARTING"
    },
    "FAC TCERT MOROCCO N°20250-174 (NVFRS-FEUILLE PRESENCE).pdf": {
        "type_objet_attendu": "formation",
        "documents_fournis": {"feuille_presence", "attestation_rib"},
        "conditions": {
            "nouveau_fournisseur": True,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture de formation - TCERT MOROCCO (nouveau fournisseur)"
    },
    "FAC PRECIA MOLEN ( RAPPORT + BL ).pdf": {
        "type_objet_attendu": "fourniture",
        "documents_fournis": {"bon_livraison_signe_cachete"},
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture de fourniture - PRECIA MOLEN"
    },
    "fact.pdf": {
        "type_objet_attendu": "transitaire",
        "documents_fournis": {"engagement_importation", "quittance_douane"},
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture transitaire - WE LOGISTICS"
    },
    "FAC EFFICIENCE MANUFACTURING N°2025-015 (Bureau d'etude).pdf": {
        "type_objet_attendu": "travaux",
        "documents_fournis": {"pv_reception_ou_attachement_signe_cachete"},
        "conditions": {
            "nouveau_fournisseur": False,
            "a_acompte": False,
            "a_retenue_garantie": False
        },
        "commentaire": "Facture de travaux - EFFICIENCE MANUFACTURING"
    }
}


# ═══════════════════════════════════════════════════════════════
# FONCTION DE TEST
# ═══════════════════════════════════════════════════════════════

def tester_documents_sur_facture(chemin_facture, verbose=True):
    """
    Teste qu'une facture réelle est correctement associée à ses documents requis.
    """
    nom_fichier = os.path.basename(chemin_facture)
    
    print(f"\n{'='*70}")
    print(f"📄 TEST DOCUMENTS : {nom_fichier}")
    print(f"{'='*70}")
    
    # 1. Vérifier que la facture existe
    if not os.path.exists(chemin_facture):
        print(f"❌ Fichier non trouvé : {chemin_facture}")
        return None
    
    # 2. Vérifier que la vérité terrain existe
    if nom_fichier not in VERITE_TERRAIN:
        print(f"⚠️ Pas de vérité terrain pour : {nom_fichier}")
        print("   Ajoutez-la dans VERITE_TERRAIN")
        return None
    
    verite = VERITE_TERRAIN[nom_fichier]
    
    # 3. Extraire les critères de la facture
    print(f"\n🔍 Extraction OCR...")
    try:
        resultats = extraire_criteres_somas(chemin_facture, verbose=False)
    except Exception as e:
        print(f"❌ Erreur OCR : {e}")
        return None
    
    # 4. Type d'objet détecté vs attendu
    type_objet_detecte = resultats.get("type_objet", "inconnu")
    type_objet_attendu = verite["type_objet_attendu"]
    
    print(f"\n📌 TYPE D'OBJET :")
    print(f"   Détecté : {type_objet_detecte}")
    print(f"   Attendu : {type_objet_attendu}")
    
    type_correct = type_objet_detecte == type_objet_attendu
    
    if type_correct:
        print(f"   ✅ Type d'objet correctement identifié")
    else:
        print(f"   ⚠️ Type d'objet différent de l'attendu")
    
    # 5. Documents requis selon le type détecté
    conditions = verite["conditions"]
    
    # Utiliser le type détecté ou le type attendu si le détecté est inconnu
    type_utilise = type_objet_detecte if type_objet_detecte != "service" else type_objet_attendu
    
    try:
        docs_requis = liste_documents_requis(
            type_utilise,
            nouveau_fournisseur=conditions.get("nouveau_fournisseur", False),
            a_acompte=conditions.get("a_acompte", False),
            a_retenue_garantie=conditions.get("a_retenue_garantie", False)
        )
    except ValueError as e:
        print(f"❌ Erreur : {e}")
        docs_requis = set()
    
    # 6. Documents fournis
    docs_fournis = verite.get("documents_fournis", set())
    
    print(f"\n📎 DOCUMENTS :")
    print(f"   Documents requis ({len(docs_requis)}) :")
    for doc in sorted(docs_requis):
        print(f"      - {doc}")
    
    print(f"\n   Documents fournis ({len(docs_fournis)}) :")
    for doc in sorted(docs_fournis):
        present = doc in docs_requis
        print(f"      {'✅' if present else '⚠️'} {doc}")
    
    # 7. Vérification
    docs_manquants = docs_requis - docs_fournis
    docs_supplementaires = docs_fournis - docs_requis
    
    print(f"\n📊 VÉRIFICATION :")
    
    if docs_manquants:
        print(f"   ❌ Documents manquants ({len(docs_manquants)}) :")
        for doc in sorted(docs_manquants):
            print(f"      - {doc}")
    else:
        print(f"   ✅ Aucun document manquant")
    
    if docs_supplementaires:
        print(f"   ℹ️ Documents supplémentaires :")
        for doc in sorted(docs_supplementaires):
            print(f"      - {doc}")
    
    # 8. Conditions
    print(f"\n📋 CONDITIONS :")
    print(f"   Nouveau fournisseur : {'Oui' if conditions.get('nouveau_fournisseur', False) else 'Non'}")
    print(f"   Acompte : {'Oui' if conditions.get('a_acompte', False) else 'Non'}")
    print(f"   Retenue de garantie : {'Oui' if conditions.get('a_retenue_garantie', False) else 'Non'}")
    
    # 9. Rapport
    tous_presents = len(docs_manquants) == 0
    
    print(f"\n{'='*70}")
    print(f"📊 RAPPORT FINAL : {nom_fichier}")
    print(f"{'='*70}")
    
    if type_correct and tous_presents:
        print("✅ FACTURE CONFORME")
        print(f"   Type d'objet : {type_objet_detecte}")
        print(f"   Tous les documents requis sont présents")
    elif type_correct and not tous_presents:
        print("⚠️ FACTURE PARTIELLEMENT CONFORME")
        print(f"   Type d'objet : {type_objet_detecte} (correct)")
        print(f"   Documents manquants : {len(docs_manquants)}")
    elif not type_correct and tous_presents:
        print("⚠️ TYPE D'OBJET INCORRECT")
        print(f"   Détecté : {type_objet_detecte}")
        print(f"   Attendu : {type_objet_attendu}")
        print(f"   Documents : tous présents")
    else:
        print("❌ FACTURE NON CONFORME")
        print(f"   Type d'objet incorrect : {type_objet_detecte} (attendu: {type_objet_attendu})")
        print(f"   Documents manquants : {len(docs_manquants)}")
    
    print("="*70)
    
    return {
        "fichier": nom_fichier,
        "type_objet_detecte": type_objet_detecte,
        "type_objet_attendu": type_objet_attendu,
        "type_correct": type_correct,
        "documents_requis": list(docs_requis),
        "documents_fournis": list(docs_fournis),
        "documents_manquants": list(docs_manquants),
        "tous_presents": tous_presents,
        "conditions": conditions,
        "conforme": type_correct and tous_presents
    }


# ═══════════════════════════════════════════════════════════════
# TEST SUR UNE FACTURE SPÉCIFIQUE - CORRIGÉ
# ═══════════════════════════════════════════════════════════════

def tester_facture_specifique(nom_fichier):
    """
    Teste une facture spécifique.
    Si le chemin contient déjà "factures/", on l'utilise tel quel.
    Sinon, on le cherche dans le dossier factures.
    """
    # Si le chemin contient déjà "factures/", l'utiliser directement
    chemin = Path(nom_fichier)
    
    # Si le chemin n'existe pas, essayer dans FACTURES_DIR
    if not chemin.exists():
        chemin = FACTURES_DIR / nom_fichier
    
    # Si le chemin n'existe toujours pas, essayer avec le nom seul
    if not chemin.exists():
        chemin = FACTURES_DIR / Path(nom_fichier).name
    
    if not chemin.exists():
        print(f"❌ Fichier non trouvé : {chemin}")
        print(f"   Recherché dans : {FACTURES_DIR}")
        print(f"   Fichiers disponibles dans factures/:")
        for f in sorted(FACTURES_DIR.glob("*.pdf")):
            print(f"      - {f.name}")
        return
    
    return tester_documents_sur_facture(str(chemin))


# ═══════════════════════════════════════════════════════════════
# TEST SUR TOUTES LES FACTURES
# ═══════════════════════════════════════════════════════════════

def tester_toutes_les_factures():
    """
    Teste toutes les factures du dossier.
    """
    print("="*70)
    print("🧪 TEST DOCUMENTS SUR FACTURES RÉELLES")
    print("="*70)
    
    factures = list(FACTURES_DIR.glob("*.pdf")) + list(FACTURES_DIR.glob("*.jpg"))
    
    if not factures:
        print(f"❌ Aucune facture trouvée dans {FACTURES_DIR}")
        return
    
    print(f"\n📁 {len(factures)} factures trouvées\n")
    
    results = []
    for facture in factures:
        if facture.name in VERITE_TERRAIN:
            result = tester_documents_sur_facture(str(facture))
            if result:
                results.append(result)
        else:
            print(f"⚠️ Pas de vérité terrain pour : {facture.name}")
    
    # ─── RAPPORT GLOBAL ──────────────────────────────────────────
    print("\n" + "="*70)
    print("📊 RAPPORT GLOBAL")
    print("="*70)
    
    if results:
        total = len(results)
        conformes = sum(1 for r in results if r["conforme"])
        types_corrects = sum(1 for r in results if r["type_correct"])
        tous_presents = sum(1 for r in results if r["tous_presents"])
        
        print(f"\n📊 Statistiques :")
        print(f"   Factures testées : {total}")
        print(f"   ✅ Conformes : {conformes} ({conformes/total*100:.1f}%)")
        print(f"   ✅ Types d'objet corrects : {types_corrects} ({types_corrects/total*100:.1f}%)")
        print(f"   ✅ Documents tous présents : {tous_presents} ({tous_presents/total*100:.1f}%)")
        
        # Détails par facture
        print(f"\n📄 Détails par facture :")
        for r in results:
            status = "✅" if r["conforme"] else "❌"
            print(f"   {status} {r['fichier']:<50} : {r['type_objet_detecte']} -> {r['type_objet_attendu']}")
        
        # Sauvegarder le rapport
        rapport_path = OUTPUT_DIR / f"rapport_documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(rapport_path, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().isoformat(),
                "total": total,
                "conformes": conformes,
                "resultats": results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Rapport sauvegardé dans : {rapport_path}")
    
    print("="*70)


# ═══════════════════════════════════════════════════════════════
# POINT D'ENTRÉE - CORRIGÉ
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    # Filtrer les arguments : ignorer ceux qui commencent par "-"
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    
    if args:
        # Tester une facture spécifique
        tester_facture_specifique(args[0])
    else:
        # Tester toutes les factures
        tester_toutes_les_factures()