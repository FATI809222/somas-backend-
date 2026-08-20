from django.db import models

# Create your models here.
# api/models.py
from django.db import models
from django.contrib.auth.models import User

# api/models.py
from django.db import models
from django.contrib.auth.models import User

class InvoiceAnalysis(models.Model):
    """Modèle pour les analyses de factures"""
    
    # ⭐ Champs existants
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    supplier = models.CharField(max_length=255, blank=True, null=True)
    is_conforme = models.BooleanField(default=False)
    anomalies = models.JSONField(default=list)
    
    # ⭐ Nouveaux champs
    score = models.IntegerField(default=0)  # Score de conformité (0-100)
    est_en_regle = models.BooleanField(null=True, blank=True, default=None)  # TVA en règle
    user_first_name = models.CharField(max_length=150, blank=True, default='')
    user_last_name = models.CharField(max_length=150, blank=True, default='')
    
    # Champs supplémentaires (pour référence)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    full_report_json = models.JSONField(default=dict, blank=True, null=True)
    
    # Champs optionnels pour plus d'informations
    type_objet = models.CharField(max_length=100, blank=True, null=True)
    objet_commande = models.TextField(blank=True, null=True)
    nb_criteres_ok = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.invoice_number or 'Sans numéro'} - {self.supplier or 'Inconnu'}"


