# list_models_old.py
import google.genai as genai
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ Clé non trouvée")
    exit(1)

try:
    genai.configure(api_key=API_KEY)
    print("✅ Configuré\n")
    
    # Lister les modèles
    models = genai.list_models()
    
    print("📌 Modèles Gemini disponibles :")
    print("-" * 60)
    
    for model in models:
        if "gemini" in model.name:
            # Vérifier si le modèle supporte generateContent
            supports_generate = "generateContent" in model.supported_generation_methods
            print(f"  - {model.name.replace('models/', '')} (generateContent: {supports_generate})")
    
except Exception as e:
    print(f"❌ Erreur: {e}")