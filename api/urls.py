# api/urls.py - VERSION CORRIGÉE
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView  # ⭐ IMPORTANT
from . import views
from .views import get_analysis_detail

urlpatterns = [
    # ═══════════════════════════════════════════════════════════════
    # AUTHENTIFICATION
    # ═══════════════════════════════════════════════════════════════
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # ⭐ AJOUTER CECI
    path('auth/logout/', views.logout, name='logout'),
    path('auth/me/', views.me, name='me'),
    
    # ═══════════════════════════════════════════════════════════════
    # ANALYSE
    # ═══════════════════════════════════════════════════════════════
    path('analyze/', views.analyze_invoice, name='analyze'),
    path('extract/', views.extract_facture, name='extract_facture'),
    
    # ═══════════════════════════════════════════════════════════════
    # HISTORIQUE
    # ═══════════════════════════════════════════════════════════════
    path('invoices/', views.get_invoices, name='get_invoices'),
    path('invoices/<int:invoice_id>/delete/', views.delete_invoice, name='delete_invoice'),
    path('invoices/<int:analysis_id>/detail/', get_analysis_detail, name='get_analysis_detail'),

    
    # ═══════════════════════════════════════════════════════════════
    # SANTÉ
    # ═══════════════════════════════════════════════════════════════
    path('health/', views.health_check, name='health'),
]