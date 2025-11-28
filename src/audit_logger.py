"""
audit_logger.py - Système de journalisation d'audit sécurisé

Ce module gère l'enregistrement immuable des actions critiques.
Il utilise deux mécanismes de sécurité :
1. Chain Hash : Chaque entrée contient le hash de l'entrée précédente.
2. HMAC : Chaque entrée est signée cryptographiquement.

Cela garantit que :
- L'historique ne peut pas être modifié sans briser la chaîne de hash.
- On ne peut pas insérer de faux logs sans la clé secrète HMAC.
"""

import hashlib
import hmac
import json
from datetime import datetime
from sqlalchemy import desc
from src.db import obtenir_session
from src.models import Journal
from src.config import Config

def calculer_hash(data):
    """
    Calcule le hash SHA-256 d'une chaîne de caractères.
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def calculer_hmac(data):
    """
    Calcule la signature HMAC-SHA256 avec la clé secrète de l'application.
    """
    secret = Config.HMAC_SECRET_KEY.encode('utf-8')
    return hmac.new(secret, data.encode('utf-8'), hashlib.sha256).hexdigest()

def log_action(utilisateur_id, action, cible=None, details=None):
    """
    Enregistre une action dans le journal d'audit sécurisé.
    
    Args:
        utilisateur_id (int): ID de l'utilisateur effectuant l'action
        action (str): Type d'action (ex: 'CONNEXION', 'DEPOT')
        cible (str, optional): Cible de l'action (ex: 'Compte 123')
        details (dict, optional): Détails supplémentaires en JSON
    
    Returns:
        bool: True si l'enregistrement a réussi, False sinon
    """
    session = obtenir_session()
    try:
        # 1. Préparer les données
        details_json = json.dumps(details) if details else None
        horodatage = datetime.utcnow()
        
        # 2. Récupérer le hash du dernier log pour la chaîne
        dernier_log = session.query(Journal).order_by(desc(Journal.id)).first()
        hash_precedent = dernier_log.hash_actuel if dernier_log else "GENESIS_HASH"
        
        # 3. Construire la chaîne de données à hasher/signer
        # Format: timestamp|user_id|action|cible|details|hash_precedent
        data_to_hash = f"{horodatage.isoformat()}|{utilisateur_id}|{action}|{cible}|{details_json}|{hash_precedent}"
        
        # 4. Calculer les sécurités
        hash_actuel = calculer_hash(data_to_hash)
        signature = calculer_hmac(data_to_hash)
        
        # 5. Créer l'entrée
        nouveau_log = Journal(
            horodatage=horodatage,
            utilisateur_id=utilisateur_id,
            action=action,
            cible=cible,
            details=details_json,
            hash_precedent=hash_precedent,
            hash_actuel=hash_actuel,
            signature_hmac=signature
        )
        
        session.add(nouveau_log)
        session.commit()
        print(f"📝 Audit: {action} enregistré avec succès.")
        return True
        
    except Exception as e:
        print(f"Erreur d'audit : {e}")
        session.rollback()
        return False
    # Note: Don't close the session here as it might interfere with other operations
    # The scoped session will be cleaned up automatically

def verifier_integrite():
    """
    Vérifie l'intégrité complète de la chaîne de logs.
    
    Parcourt tous les logs et vérifie :
    1. Que le hash_precedent correspond bien au hash_actuel du log d'avant.
    2. Que le hash_actuel est valide par rapport aux données.
    3. Que la signature HMAC est valide.
    
    Returns:
        tuple: (bool, list) - (Valide?, Liste des erreurs trouvées)
    """
    session = obtenir_session()
    logs = session.query(Journal).order_by(Journal.id).all()
    session.close()
    
    erreurs = []
    hash_attendu_precedent = "GENESIS_HASH"
    
    for log in logs:
        # Reconstruire les données
        data_to_hash = f"{log.horodatage.isoformat()}|{log.utilisateur_id}|{log.action}|{log.cible}|{log.details}|{log.hash_precedent}"
        
        # Vérification 1 : Chaînage
        if log.hash_precedent != hash_attendu_precedent:
            erreurs.append(f"Log #{log.id} : Rupture de chaîne (Hash précédent invalide)")
        
        # Vérification 2 : Hash actuel
        hash_calcule = calculer_hash(data_to_hash)
        if log.hash_actuel != hash_calcule:
            erreurs.append(f"Log #{log.id} : Données corrompues (Hash invalide)")
            
        # Vérification 3 : Signature HMAC
        hmac_calcule = calculer_hmac(data_to_hash)
        if log.signature_hmac != hmac_calcule:
            erreurs.append(f"Log #{log.id} : Signature falsifiée (HMAC invalide)")
            
        # Mise à jour pour le prochain tour
        hash_attendu_precedent = log.hash_actuel
        
    est_valide = len(erreurs) == 0
    return est_valide, erreurs

"""
Interface web pour le système d'audit sécurisé
"""

from flask import (
    Blueprint, flash, g, render_template, request, url_for, redirect
)
from src.auth import permission_required
from src.db import obtenir_session
from src.models import Journal
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
import json

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

@audit_bp.route('/')
@permission_required('audit.view')
def index():
    """Affiche la liste des entrées du journal d'audit."""
    page = int(request.args.get('page', 1))
    per_page = 50
    
    session = obtenir_session()
    # Récupérer les entrées avec pagination (plus récentes en premier)
    total_entries = session.query(Journal).count()
    entries = session.query(Journal)\
        .options(joinedload(Journal.utilisateur))\
        .order_by(desc(Journal.id))\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    session.close()
    
    total_pages = (total_entries + per_page - 1) // per_page
    
    return render_template('audit/index.html', 
                         entries=entries, 
                         page=page, 
                         total_pages=total_pages,
                         total_entries=total_entries)

@audit_bp.route('/verifier')
@permission_required('audit.verify')
def verify():
    """Vérifie l'intégrité du journal d'audit."""
    valide, erreurs = verifier_integrite()
    
    if valide:
        flash('L\'intégrité du journal d\'audit est validée.', 'success')
    else:
        flash(f'L\'intégrité du journal est compromise ! {len(erreurs)} erreur(s) détectée(s).', 'danger')
    
    return render_template('audit/verify.html', valide=valide, erreurs=erreurs)

@audit_bp.route('/<int:id>')
@permission_required('audit.view')
def view(id):
    """Affiche les détails d'une entrée d'audit."""
    session = obtenir_session()
    entry = session.query(Journal)\
        .options(joinedload(Journal.utilisateur))\
        .filter_by(id=id)\
        .first()
    session.close()
    
    if entry is None:
        flash('Entrée d\'audit introuvable.', 'danger')
        return redirect(url_for('audit.index'))
    
    # Parser les détails JSON si présents
    details = None
    if entry.details:
        try:
            details = json.loads(entry.details)
        except:
            details = entry.details
    
    return render_template('audit/view.html', entry=entry, details=details)

if __name__ == '__main__':
    # Test rapide si exécuté directement
    print("=== Test du système d'audit ===")
    
    # 1. Créer un log
    print("\n1. Création d'un log de test...")
    log_action(1, "TEST_ACTION", "Système", {"test": "ok"})
    
    # 2. Vérifier l'intégrité
    print("\n2. Vérification de l'intégrité...")
    valide, erreurs = verifier_integrite()
    
    if valide:
        print("Intégrité du journal : VALIDE")
    else:
        print("Intégrité du journal : INVALIDE")
        for err in erreurs:
            print(f"  - {err}")
