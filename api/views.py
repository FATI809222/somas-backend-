import os
import tempfile
import traceback
import re
import json
from datetime import datetime
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

# ⭐ IMPORTANT : Utiliser extractor.py (OCR + phi3) au lieu de ocr_extractor.py seul
from core.extractor import extraire_facture
from core.checklist_config import verifier_documents_requis


# ═══════════════════════════════════════════════════════════════
# ⭐ FONCTION DE CONVERSION DES DATES (AJOUTÉE)
# ═══════════════════════════════════════════════════════════════

def convertir_dates_en_strings(obj):
    """
    Convertit récursivement tous les objets datetime en chaînes ISO.
    """
    if isinstance(obj, dict):
        return {k: convertir_dates_en_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convertir_dates_en_strings(v) for v in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()  # Convertit datetime en string
    else:
        return obj


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def health_check(request):
    """Vérifie que l'API est en ligne."""
    return Response({
        'status': 'OK',
        'service': 'SOMAS Compliance API',
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat()
    })

# ═══════════════════════════════════════════════════════════════
# ANALYSE FACTURE - AVEC extractor.py (OCR + phi3)
# ═══════════════════════════════════════════════════════════════

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def analyze_invoice(request):
    """
    Analyse une facture avec OCR + phi3 et retourne la conformité SOMAS.
    POST /api/analyze/
    Body: file (multipart/form-data)
    """
    try:
        print("="*60)
        print("🔍 ANALYSE FACTURE - OCR + phi3")
        print("="*60)
        
        # 1. Récupérer le fichier
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'Aucun fichier fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"📄 Fichier reçu : {file.name}")
        print(f"📄 Taille : {file.size} octets")
        
        # 2. Sauvegarder temporairement le fichier
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        
        print(f"💾 Fichier sauvegardé : {tmp_path}")
        
        try:
            # ⭐ 3. Analyser AVEC extractor.py (OCR + phi3)
            print("🔍 Appel de extraire_facture (OCR + phi3)...")
            resultat_complet = extraire_facture(tmp_path)
            print("✅ Extraction terminée")
            
            # ⭐ 4. Extraire les données du résultat
            resultats = resultat_complet.get('checklist_somas', {})
            conformite = resultat_complet.get('conformite', {})
            objet_commande = resultat_complet.get('objet_commande', 'Non détecté')
            date_facture = resultat_complet.get('date_facture')
            fournisseur = resultat_complet.get('fournisseur')
            num_facture = resultat_complet.get('numéro_facture')
            montant_ttc = resultat_complet.get('montant_ttc')
            est_en_regle = resultat_complet.get('est_en_regle')
            
            print(f"📋 Objet commande : {objet_commande}")
            print(f"📋 Conformité : {conformite.get('est_conforme', False)}")
            print(f"📋 Est en règle : {est_en_regle}")
            
        except Exception as e:
            print(f"❌ Erreur extraction : {e}")
            print(traceback.format_exc())
            raise
        finally:
            # 5. Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                print(f"🗑️ Fichier temporaire supprimé : {tmp_path}")
        
        # 6. Construire la réponse
        return Response({
            'success': True,
            'is_conforme': conformite.get('est_conforme', False),
            'score': 100 - (conformite.get('nb_erreurs', 0) * 10),
            'elements_manquants': conformite.get('erreurs', []),
            'result': {
                # Données extractor.py
                'objet_commande': objet_commande,
                'date_facture': date_facture,
                'fournisseur': fournisseur,
                'numéro_facture': num_facture,
                'montant_ttc': montant_ttc,
                'est_en_regle': est_en_regle,  # ⭐ AJOUTÉ
                # Checklist SOMAS
                'checklist_somas': resultats,
                # Conformité
                'conformite': conformite,
                # Métadonnées
                '_metadata': resultat_complet.get('_metadata', {})
            }
        })
        
    except Exception as e:
        print("="*60)
        print("❌ ERREUR DANS ANALYZE_INVOICE")
        print(f"   Message : {e}")
        print(f"   Traceback :")
        print(traceback.format_exc())
        print("="*60)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ═══════════════════════════════════════════════════════════════
# ⭐ FONCTION D'ENREGISTREMENT (AVEC full_report_json CORRIGÉ)
# ═══════════════════════════════════════════════════════════════

def enregistrer_analyse(request, result, file_name, file_size=0):
    """
    Enregistre automatiquement l'analyse dans la base de données.
    """
    try:
        from .models import InvoiceAnalysis
        from django.contrib.auth.models import User
        from rest_framework_simplejwt.tokens import AccessToken
        from datetime import datetime
        
        print("="*60)
        print("💾 ENREGISTREMENT EN BASE DE DONNÉES")
        print("="*60)
        
        # 1. Récupérer l'utilisateur depuis le token
        user = None
        auth_header = request.headers.get('Authorization')
        user_info = {}
        
        if auth_header and auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(' ')[1]
                access_token = AccessToken(token)
                user_id = access_token.get('user_id')
                user = User.objects.get(id=user_id)
                print(f"👤 Utilisateur: {user.username}")
                user_info = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
                print(f"📋 Nom: {user.first_name} {user.last_name}")
            except Exception as e:
                print(f"⚠️ Erreur authentification: {e}")
        
        # Si pas d'utilisateur, utiliser le premier ou créer un anonyme
        if not user:
            user = User.objects.first()
            if not user:
                user = User.objects.create_user(
                    username='anonymous',
                    password='anonymous123',
                    email='anonymous@test.com'
                )
            print(f"👤 Utilisateur par défaut: {user.username}")
            user_info = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        
        # 2. Extraire les données
        conformite = result.get('conformite', {})
        num_facture = result.get('numéro_facture', '')
        fournisseur = result.get('fournisseur', '')
        est_conforme = conformite.get('est_conforme', False)
        erreurs = conformite.get('erreurs', [])
        score = 100 - (len(erreurs) * 10)
        
        # ⭐ Récupérer est_en_regle
        est_en_regle = result.get('est_en_regle')
        if est_en_regle is None:
            est_en_regle = result.get('checklist_somas', {}).get('est_en_regle')
        
        print(f"📋 Numéro: {num_facture}")
        print(f"🏢 Fournisseur: {fournisseur}")
        print(f"✅ Conforme: {est_conforme}")
        print(f"⚠️ Anomalies: {len(erreurs)}")
        print(f"📋 Est en règle: {est_en_regle}")
        print(f"👤 Nom: {user_info.get('first_name', '')} {user_info.get('last_name', '')}")
        
        # 3. ⭐ CRÉER L'ENREGISTREMENT AVEC full_report_json
        invoice = InvoiceAnalysis.objects.create(
            user=user,
            invoice_number=num_facture or 'INCONNU',
            supplier=fournisseur or 'Fournisseur non détecté',
            is_conforme=est_conforme,
            anomalies=erreurs,
            score=score,
            file_name=file_name if isinstance(file_name, str) else 'fichier.pdf',
            est_en_regle=est_en_regle,
            user_first_name=user.first_name,
            user_last_name=user.last_name,
            
            # ⭐⭐⭐ CORRECTION ICI ⭐⭐⭐
            full_report_json=convertir_dates_en_strings(result)  # ✅ Convertit les dates avant stockage
        )
        
        # 4. Stocker l'ID et les infos utilisateur pour la réponse
        request._analysis_id = invoice.id
        request._user_info = user_info
        
        print(f"✅ Enregistrement réussi - ID: {invoice.id}")
        print(f"   👤 Nom: {invoice.user_first_name} {invoice.user_last_name}")
        print("="*60)
        
        return invoice
        
    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement: {e}")
        print(traceback.format_exc())
        return None


# ═══════════════════════════════════════════════════════════════
# EXTRACTION FACTURE - ENDPOINT SANS AUTH (POUR TESTS)
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
def extract_facture(request):
    """
    ENDPOINT D'EXTRACTION - AVEC ENREGISTREMENT AUTOMATIQUE EN BDD
    POST /api/extract/
    Body: file (multipart/form-data)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        print("="*60)
        print("📄 EXTRACTION FACTURE - extract_facture")
        print("="*60)
        
        # 1. Vérifier si c'est un JSON avec file_path
        if not request.FILES:
            try:
                data = json.loads(request.body)
                file_path = data.get('file_path')
                if file_path:
                    print(f"📄 Chemin fichier: {file_path}")
                    if not os.path.exists(file_path):
                        return JsonResponse({
                            'success': False,
                            'error': f'Fichier non trouvé: {file_path}'
                        }, status=400)
                    
                    result = extraire_facture(file_path)
                    
                    # ⭐ ENREGISTRER LE RÉSULTAT
                    enregistrer_analyse(request, result, os.path.basename(file_path))
                    
                    return JsonResponse({
                        'success': True,
                        'data': result,
                        'saved': True,
                        'analysis_id': getattr(request, '_analysis_id', None),
                        'user': getattr(request, '_user_info', None)
                    })
            except json.JSONDecodeError:
                pass
            return JsonResponse({'error': 'Aucun fichier fourni'}, status=400)
        
        # 2. Récupérer le fichier uploadé
        file = request.FILES['file']
        print(f"📄 Fichier reçu : {file.name}")
        print(f"📄 Taille : {file.size} octets")
        print(f"📄 Type : {file.content_type}")
        
        # ⭐ Récupérer type_fournisseur depuis le formulaire
        type_fournisseur = request.POST.get('type_objet_force')
        if type_fournisseur:
            print(f"📋 Type fournisseur reçu: {type_fournisseur}")
        else:
            print(f"📋 Type fournisseur: Non spécifié")
        
        # 3. Sauvegarder temporairement
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        
        print(f"💾 Fichier sauvegardé : {tmp_path}")
        
        try:
            # 4. Appeler extraire_facture AVEC type_fournisseur
            print("🔍 Appel de extraire_facture...")
            result = extraire_facture(tmp_path, type_fournisseur=type_fournisseur)
            print("✅ Extraction terminée avec succès")
            
            # ⭐⭐⭐ 5. ENREGISTRER DANS LA BASE DE DONNÉES
            enregistrer_analyse(request, result, file.name, file.size)
            
            # ⭐ Récupérer la liste des erreurs depuis le rapport
            conformite = result.get('conformite', {})
            erreurs = conformite.get('erreurs', [])

            response_data = {
                'success': True,
                'data': result,
                'saved': True,
                'analysis_id': getattr(request, '_analysis_id', None),
                'user': getattr(request, '_user_info', None),
                # ⭐⭐⭐ AJOUTEZ CETTE LIGNE ICI ⭐⭐⭐
                'elements_manquants': erreurs,  # C'est ce que le Frontend attend
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            print(f"❌ Erreur extraction: {e}")
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
            
        finally:
            # 6. Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                print(f"🗑️ Fichier temporaire supprimé")
        
    except Exception as e:
        print("="*60)
        print("❌ ERREUR DANS extract_facture")
        print(f"   Message : {e}")
        print(traceback.format_exc())
        print("="*60)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# ═══════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ═══════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])  # ⭐ PUBLIC - Pas besoin de token
def register(request):
    """
    Crée un nouveau compte utilisateur.
    POST /api/auth/register/
    Body: { username, email, password, first_name, last_name }
    """
    try:
        data = request.data
        print("📝 Données d'inscription reçues:", data)
        
        required_fields = ['username', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return Response(
                    {'error': f'Le champ {field} est obligatoire'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        username = data['username']
        email = data['email']
        password = data['password']
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Ce nom d\'utilisateur existe déjà'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Cet email est déjà utilisé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(password) < 8:
            return Response(
                {'error': 'Le mot de passe doit contenir au moins 8 caractères'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ⭐ Créer l'utilisateur avec first_name et last_name
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        print(f"✅ Utilisateur créé: {username} ({first_name} {last_name})")
        
        refresh = RefreshToken.for_user(user)
        
        response_data = {
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        
        print("📤 Réponse inscription:", response_data)
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"❌ Erreur inscription: {e}")
        print(traceback.format_exc())
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # ⭐ PUBLIC - Pas besoin de token
def login(request):
    """
    Connecte un utilisateur et retourne un token JWT.
    POST /api/auth/login/
    Body: { username, password }
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        
        print(f"🔑 Tentative de login: {username}")
        
        if not username or not password:
            return Response(
                {'error': 'Nom d\'utilisateur et mot de passe requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'error': 'Identifiants incorrects'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'Compte désactivé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        refresh = RefreshToken.for_user(user)
        
        response_data = {
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        
        print(f"✅ Login réussi: {username} ({user.first_name} {user.last_name})")
        
        return Response(response_data)
        
    except Exception as e:
        print(f"❌ Erreur login: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # ⭐ PUBLIC - Pas besoin de token
def logout(request):
    """Déconnecte l'utilisateur."""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'success': True})
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])  # ⭐ PROTÉGÉ - Token requis
def me(request):
    """Récupère les informations de l'utilisateur connecté."""
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_authenticated': True,
    })


# ═══════════════════════════════════════════════════════════════
# HISTORIQUE ET STATISTIQUES
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_history(request):
    """Récupère l'historique des analyses de l'utilisateur."""
    try:
        from .models import InvoiceAnalysis
        
        invoices = InvoiceAnalysis.objects.all()  # ✅ Plus de filtre ! Toutes les factures
        
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        start = (page - 1) * per_page
        end = start + per_page
        
        total = invoices.count()
        items = invoices[start:end]
        
        return Response({
            'total': total,
            'page': page,
            'per_page': per_page,
            'items': [{
                'id': inv.id,
                'file_name': inv.file_name,
                'is_conforme': inv.is_conforme,
                'score': inv.score,
                'type_objet': inv.type_objet,
                'objet_commande': inv.objet_commande,
                'nb_criteres_ok': inv.nb_criteres_ok,
                'created_at': inv.created_at.isoformat(),
                'est_en_regle': inv.est_en_regle,
                'user_first_name': inv.user_first_name,
                'user_last_name': inv.user_last_name,
            } for inv in items]
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_invoices(request):
    """
    Récupère TOUTES les analyses (tous utilisateurs confondus) avec pagination.
    GET /api/invoices/
    Query params: 
        - page: int
        - per_page: int
        - status: 'conforme' | 'non_conforme'
        - search: string
    """
    try:
        from .models import InvoiceAnalysis
        from django.db.models import Q
        
        # ⭐ CORRECTION ICI : On prend TOUTES les factures, pas seulement celles de l'utilisateur
        invoices = InvoiceAnalysis.objects.all()
        
        # Filtres
        status_filter = request.GET.get('status')
        if status_filter == 'conforme':
            invoices = invoices.filter(is_conforme=True)
        elif status_filter == 'non_conforme':
            invoices = invoices.filter(is_conforme=False)
        
        search = request.GET.get('search')
        if search:
            invoices = invoices.filter(
                Q(invoice_number__icontains=search) |
                Q(supplier__icontains=search)
            )
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        start = (page - 1) * per_page
        end = start + per_page
        
        total = invoices.count()
        items = invoices[start:end]
        
        return Response({
            'total': total,
            'page': page,
            'per_page': per_page,
            'items': [{
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'supplier': inv.supplier,
                'is_conforme': inv.is_conforme,
                'file_name': inv.file_name,
                'created_at': inv.created_at.isoformat(),
                'anomalies': inv.anomalies,
                'anomalies_count': len(inv.anomalies) if isinstance(inv.anomalies, list) else 0,
                'est_en_regle': inv.est_en_regle,
                'user_first_name': inv.user_first_name,
                'user_last_name': inv.user_last_name,
            } for inv in items]
        })
        
    except Exception as e:
        print(f"❌ Erreur get_invoices: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_invoice(request, invoice_id):
    """
    Supprime une analyse.
    DELETE /api/invoices/<id>/delete/
    """
    try:
        from .models import InvoiceAnalysis
        
        invoice = InvoiceAnalysis.objects.get(id=invoice_id, user=request.user)
        invoice.delete()
        
        return Response({
            'success': True,
            'message': f'Analyse {invoice_id} supprimée'
        })
        
    except InvoiceAnalysis.DoesNotExist:
        return Response(
            {'error': 'Analyse non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stats(request):
    """Récupère les statistiques pour le dashboard."""
    try:
        from .models import InvoiceAnalysis
        
        user = request.user
        invoices = InvoiceAnalysis.objects.filter(user=user)
        
        total = invoices.count()
        conformes = invoices.filter(is_conforme=True).count()
        non_conformes = total - conformes
        
        recent = invoices[:5]
        
        type_stats = {}
        for inv in invoices:
            t = inv.type_objet or 'inconnu'
            type_stats[t] = type_stats.get(t, 0) + 1
        
        monthly_stats = {}
        for inv in invoices:
            month = inv.created_at.strftime('%Y-%m')
            if month not in monthly_stats:
                monthly_stats[month] = {
                    'total': 0,
                    'conformes': 0,
                    'score_total': 0
                }
            monthly_stats[month]['total'] += 1
            if inv.is_conforme:
                monthly_stats[month]['conformes'] += 1
            monthly_stats[month]['score_total'] += inv.score
        
        monthly_rates = {}
        for month, data in monthly_stats.items():
            monthly_rates[month] = {
                'total': data['total'],
                'conformes': data['conformes'],
                'taux': round((data['conformes'] / data['total']) * 100, 1) if data['total'] > 0 else 0,
                'score_moyen': round(data['score_total'] / data['total'], 1) if data['total'] > 0 else 0
            }
        
        return Response({
            'total': total,
            'conformes': conformes,
            'non_conformes': non_conformes,
            'taux_conformite': round((conformes / total * 100), 1) if total > 0 else 0,
            'recent': [{
                'id': inv.id,
                'file_name': inv.file_name,
                'is_conforme': inv.is_conforme,
                'score': inv.score,
                'objet_commande': inv.objet_commande,
                'created_at': inv.created_at.isoformat(),
                'est_en_regle': inv.est_en_regle,
                'user_first_name': inv.user_first_name,
                'user_last_name': inv.user_last_name,
            } for inv in recent],
            'type_stats': type_stats,
            'monthly_stats': monthly_rates
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ═══════════════════════════════════════════════════════════════
# ⭐⭐ NOUVEAU : API POUR RÉCUPÉRER LE RAPPORT COMPLET ⭐⭐
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analysis_detail(request, analysis_id):
    """
    Récupère le détail complet d'une analyse (checklist incluse).
    GET /api/invoices/<id>/detail/
    """
    try:
        from .models import InvoiceAnalysis
        
        # ⭐ Récupérer l'analyse (on autorise tous les utilisateurs connectés)
        invoice = InvoiceAnalysis.objects.get(id=analysis_id)
        
        return Response({
            'success': True,
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'supplier': invoice.supplier,
            'is_conforme': invoice.is_conforme,
            'full_report': invoice.full_report_json,  # ⭐ Le rapport complet JSON
            'created_at': invoice.created_at.isoformat(),
            'user_first_name': invoice.user_first_name,
            'user_last_name': invoice.user_last_name,
        })
        
    except InvoiceAnalysis.DoesNotExist:
        return Response(
            {'error': 'Analyse non trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )