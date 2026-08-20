# tests/tests_factures_reelles.py

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# AJOUTER LE CHEMIN src/ POUR LES IMPORTS
# ═══════════════════════════════════════════════════════════════

# Ajouter le dossier parent (Stage SOMAS) et src/ au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Maintenant l'import fonctionne
from ocr_extractor import extraire_criteres_somas

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

FACTURES_DIR = Path("factures")
OUTPUT_DIR = Path("outputs/ocr_tests")

# Créer le dossier de sortie
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# ANALYSE MANUELLE DES FACTURES (VÉRITÉ TERRAIN)
# ═══════════════════════════════════════════════════════════════

VERITE_TERRAIN = {
    "FAC8.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    
    "FACT.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": False,
        "cachet_ok": False,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Manque RC, cachet/signature"
    },
    "FAC3.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    "FAC5.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    "FAC4.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    "FAC6.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
      "FAC7.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    "fact.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    "FAC.pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": True,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Tous les champs sont présents"
    },
    # ═══════════════════════════════════════════════════════════
    # FACTURE : EFFICIENCE MANUFACTURING (Bureau d'études)
    # ═══════════════════════════════════════════════════════════
    "Fct2.pdf": {
        "date_valide": True,           # Date : 14/08/2025 (récente)
        "if_ok": True,                 # IF : 01085269 (dans le pied de page)
        "ice_ok": True,                # ICE : 000000695000053 (SOMAS)
        "cnss_ok": True,               # CNSS : 156.9427 (dans le pied de page)
        "rc_ok": True,                 # RC : 2405 Mohammedia (sur la facture)
        "cachet_ok": False,            # ❌ Pas de cachet visible (image en bas de page)
        "montant_lettres_ok": True,    # Montant en lettres : "Quatre- Vingt- Quatorze Mille..."
        "objet_commande_ok": True,     # Objet : "Travaux complémentaires de réalisation réseau incendie"
        "commentaire": "Manque cachet/signature (image en bas non détectée)"
    },
    # ═══════════════════════════════════════════════════════════
    # FACTURE : PRECIA MOLEN (RAPPORT + BL)
    # ═══════════════════════════════════════════════════════════
    "FAC PRECIA MOLEN ( RAPPORT + BL ).pdf": {
        "date_valide": True,           # Date : 11/06/2024 (mais selon votre vérité terrain, True)
        "if_ok": True,                 # IF : 01085269 (dans le pied de page)
        "ice_ok": True,                # ICE : 000000695000053 (dans le pied de page)
        "cnss_ok": True,               # CNSS : 156.9427 (dans le pied de page)
        "rc_ok": True,                 # RC : 2405 Mohammedia (dans le pied de page)
        "cachet_ok": True,             # Cachet présent (page 3 : signature + cachet client)
        "montant_lettres_ok": True,    # Montant en lettres : "NEUF MILLE SIX CENTS DIRHAMS HORS TAXE"
        "objet_commande_ok": True,     # Objet : "Entretien levier de vannes bras de chargement CMH"
        "commentaire": "Tous les champs sont présents - Maintenance/Fourniture"
    },
    # ═══════════════════════════════════════════════════════════
    # FACTURE : FAC EFFICIENCE MANUFACTURING N°2025-015
    # ═══════════════════════════════════════════════════════════
    "FAC EFFICIENCE MANUFACTURING N°2025-015 (Bureau d'etude).pdf": {
        "date_valide": True,
        "if_ok": True,
        "ice_ok": True,
        "cnss_ok": True,
        "rc_ok": True,
        "cachet_ok": False,
        "montant_lettres_ok": True,
        "objet_commande_ok": True,
        "commentaire": "Manque cachet/signature"
    }
}

# ═══════════════════════════════════════════════════════════════
# FONCTION DE TEST
# ═══════════════════════════════════════════════════════════════

def tester_ocr_sur_facture(chemin_facture, verbose=True):
    """
    Teste l'OCR sur une facture et compare avec la vérité terrain.
    """
    nom_fichier = os.path.basename(chemin_facture)
    
    print(f"\n{'='*60}")
    print(f"📄 Test OCR : {nom_fichier}")
    print(f"{'='*60}")
    
    # 1. Vérifier si la facture existe
    if not os.path.exists(chemin_facture):
        print(f"❌ Fichier non trouvé : {chemin_facture}")
        return None
    
    # 2. Vérifier si la vérité terrain existe
    if nom_fichier not in VERITE_TERRAIN:
        print(f"⚠️ Pas de vérité terrain pour : {nom_fichier}")
        print("   Ajoutez-la dans VERITE_TERRAIN")
        return None
    
    verite = VERITE_TERRAIN[nom_fichier]
    
    # 3. Lancer l'extraction
    print(f"\n🔍 Extraction OCR...")
    try:
        resultats = extraire_criteres_somas(chemin_facture, verbose=False)
    except Exception as e:
        print(f"❌ Erreur OCR : {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # 4. Comparer avec la vérité terrain
    print(f"\n📊 Comparaison avec la vérité terrain :")
    print("-" * 60)
    
    comparaison = {
        "fichier": nom_fichier,
        "commentaire": verite.get("commentaire", ""),
        "resultats": {}
    }
    
    champs_a_tester = [
        "date_valide",
        "if_ok", 
        "ice_ok",
        "cnss_ok",
        "rc_ok",
        "cachet_ok",
        "montant_lettres_ok",
        "objet_commande_ok"
    ]
    
    nb_correct = 0
    nb_total = len(champs_a_tester)
    
    for champ in champs_a_tester:
        attendu = verite.get(champ, False)
        obtenu = resultats.get(champ, 0) == 1
        
        est_correct = (attendu == obtenu)
        if est_correct:
            nb_correct += 1
        
        symbole = "✅" if est_correct else "❌"
        status_attendu = "PRÉSENT" if attendu else "ABSENT"
        status_obtenu = "PRÉSENT" if obtenu else "ABSENT"
        
        comparaison["resultats"][champ] = {
            "attendu": attendu,
            "obtenu": obtenu,
            "correct": est_correct
        }
        
        print(f"   {symbole} {champ:<20} : attendu={status_attendu:>7}, obtenu={status_obtenu:>7}")
    
    # 5. Statistiques
    precision = (nb_correct / nb_total) * 100 if nb_total > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"📊 STATISTIQUES :")
    print(f"   {nom_fichier}")
    print(f"   ✅ Correct : {nb_correct}/{nb_total} ({precision:.1f}%)")
    print(f"   💬 Commentaire : {verite.get('commentaire', '')}")
    
    # 6. Détails supplémentaires
    print(f"\n📋 DÉTAILS DE L'EXTRACTION :")
    print(f"   Mots OCR : {resultats.get('nb_mots_ocr', 0)}")
    print(f"   Confiance moyenne : {resultats.get('confiance_moyenne', 0):.1f}%")
    print(f"   Date trouvée : {resultats.get('date_trouvee', '❌ Non trouvée')}")
    print(f"   Type objet détecté : {resultats.get('type_objet', '❌ Non détecté')}")
    
    # 7. Résumé des champs manquants selon l'OCR
    manquants_ocr = []
    for champ in champs_a_tester:
        if resultats.get(champ, 0) == 0:
            manquants_ocr.append(champ)
    
    if manquants_ocr:
        print(f"\n⚠️ Champs non détectés par l'OCR :")
        for champ in manquants_ocr:
            print(f"   ❌ {champ}")
    else:
        print(f"\n✅ Tous les champs ont été détectés !")
    
    print("="*60)
    
    comparaison["precision"] = precision
    comparaison["nb_correct"] = nb_correct
    comparaison["nb_total"] = nb_total
    comparaison["manquants_ocr"] = manquants_ocr
    
    return comparaison

# ═══════════════════════════════════════════════════════════════
# TEST SUR UNE FACTURE SPÉCIFIQUE
# ═══════════════════════════════════════════════════════════════

def tester_facture_specifique(nom_fichier):
    """
    Teste une facture spécifique.
    """
    # Vérifier si le chemin est absolu ou relatif
    if os.path.exists(nom_fichier):
        chemin = nom_fichier
    else:
        chemin = FACTURES_DIR / nom_fichier
    
    if not os.path.exists(chemin):
        print(f"❌ Fichier non trouvé : {chemin}")
        print(f"   Recherché dans : {FACTURES_DIR}")
        return
    
    tester_ocr_sur_facture(str(chemin))

# ═══════════════════════════════════════════════════════════════
# TEST SUR TOUTES LES FACTURES
# ═══════════════════════════════════════════════════════════════

def tester_toutes_les_factures():
    """
    Teste l'OCR sur toutes les factures du dossier.
    """
    print("="*60)
    print("🧪 TEST DE PERFORMANCE OCR")
    print("="*60)
    
    # Récupérer toutes les factures
    factures = list(FACTURES_DIR.glob("*.pdf")) + list(FACTURES_DIR.glob("*.jpg"))
    
    if not factures:
        print(f"❌ Aucune facture trouvée dans {FACTURES_DIR}")
        print("   Placez vos factures dans le dossier 'factures/'")
        return
    
    print(f"\n📁 {len(factures)} factures trouvées :")
    for f in factures:
        print(f"   - {f.name}")
    
    # Tester chaque facture
    results = []
    for facture in factures:
        result = tester_ocr_sur_facture(str(facture))
        if result:
            results.append(result)
    
    # ─── RAPPORT GLOBAL ──────────────────────────────────────────
    print("\n" + "="*60)
    print("📊 RAPPORT GLOBAL")
    print("="*60)
    
    if results:
        total_correct = sum(r["nb_correct"] for r in results)
        total_possible = sum(r["nb_total"] for r in results)
        precision_globale = (total_correct / total_possible) * 100 if total_possible > 0 else 0
        
        print(f"\n📊 Performance globale :")
        print(f"   ✅ Correct : {total_correct}/{total_possible} ({precision_globale:.1f}%)")
        print(f"   📄 Factures testées : {len(results)}")
        
        # Détails par facture
        print(f"\n📄 Détails par facture :")
        for r in results:
            print(f"   {r['fichier']:<30} : {r['nb_correct']}/{r['nb_total']} ({r['precision']:.1f}%)")
        
        # Champs les plus souvent manquants
        print(f"\n⚠️ Champs les plus souvent manquants :")
        champ_manquant_count = {}
        for r in results:
            for champ in r["manquants_ocr"]:
                champ_manquant_count[champ] = champ_manquant_count.get(champ, 0) + 1
        
        if champ_manquant_count:
            for champ, count in sorted(champ_manquant_count.items(), key=lambda x: x[1], reverse=True):
                print(f"   ❌ {champ} : manquant dans {count}/{len(results)} factures")
        else:
            print(f"   ✅ Aucun champ systématiquement manquant")
        
        # Sauvegarder le rapport
        rapport_path = OUTPUT_DIR / f"rapport_ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(rapport_path, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().isoformat(),
                "precision_globale": precision_globale,
                "resultats": results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Rapport sauvegardé dans : {rapport_path}")
    
    print("="*60)

# ═══════════════════════════════════════════════════════════════
# FONCTION POUR AFFICHER LE TEXTE OCR DÉTAILLÉ (AJOUTÉE)
# ═══════════════════════════════════════════════════════════════

def afficher_detail_ocr(chemin_facture):
    """
    Affiche le texte OCR extrait d'une facture avec tous les détails.
    Utilisation : python tests/tests_factures_reelles.py --debug factures/FAC.pdf
    """
    print("\n" + "="*70)
    print("🔍 DÉTAIL COMPLET DE L'OCR")
    print("="*70)
    
    try:
        resultats = extraire_criteres_somas(chemin_facture, verbose=True)
        
        print("\n📝 TEXTE OCR COMPLET :")
        print("-"*70)
        texte = resultats.get('texte_extrait', '')
        print(texte)
        print("-"*70)
        
        print(f"\n📊 STATISTIQUES OCR :")
        print(f"   Mots extraits : {resultats.get('nb_mots_ocr', 0)}")
        print(f"   Confiance moyenne : {resultats.get('confiance_moyenne', 0):.1f}%")
        print(f"   Date trouvée : {resultats.get('date_trouvee', 'Non trouvée')}")
        print(f"   Type objet détecté : {resultats.get('type_objet', 'Non détecté')}")
        
        print("\n📋 CHAMPS DÉTECTÉS :")
        champs = [
            ('date_valide', 'Date valide'),
            ('if_ok', 'IF (Identifiant Fiscal)'),
            ('ice_ok', 'ICE Fournisseur'),
            ('cnss_ok', 'CNSS'),
            ('rc_ok', 'RC (Registre de Commerce)'),
            ('cachet_ok', 'Cachet/Signature'),
            ('montant_lettres_ok', 'Montant en lettres'),
            ('objet_commande_ok', 'Objet de commande')
        ]
        
        for champ, label in champs:
            valeur = resultats.get(champ, False)
            status = "✅ Détecté" if valeur else "❌ Non détecté"
            print(f"   {status} : {label}")
        
        print("\n🔎 VALEURS EXTRAITES :")
        valeurs = [
            ('ice_valeur', 'ICE'),
            ('cnss_valeur', 'CNSS'),
            ('rc_valeur', 'RC'),
            ('rib_valeur', 'RIB')
        ]
        for champ, label in valeurs:
            valeur = resultats.get(champ, 'Non trouvé')
            print(f"   {label} : {valeur}")
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()

# ═══════════════════════════════════════════════════════════════
# POINT D'ENTRÉE (MODIFIÉ POUR SUPPORTER --debug)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        fichier = sys.argv[1]
        
        # Si --debug est passé, afficher le texte OCR complet
        if fichier == "--debug" and len(sys.argv) > 2:
            afficher_detail_ocr(sys.argv[2])
        elif fichier == "-v":
            tester_toutes_les_factures()
        else:
            tester_facture_specifique(fichier)
    else:
        # Tester toutes les factures
        tester_toutes_les_factures()