# list_models.py
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

print("="*60)
print("📋 LISTE DES MODÈLES DISPONIBLES")
print("="*60)

if not API_KEY:
    print("❌ Clé non trouvée")
    exit(1)

try:
    client = genai.Client(api_key=API_KEY)
    print("✅ Client créé\n")
    
    # Lister tous les modèles
    models = client.models.list()
    
    print("📌 Modèles Gemini disponibles :")
    print("-" * 40)
    
    for model in models:
        if "gemini" in model.name:
            # Vérifier si le modèle supporte generateContent
            supported = "generateContent" in str(model.supported_generation_methods) if hasattr(model, 'supported_generation_methods') else "inconnu"
            print(f"  - {model.name} (support: {supported})")
    
    print("-" * 40)
    print("✅ Liste des modèles affichée")
    
except Exception as e:
    print(f"❌ Erreur: {e}")