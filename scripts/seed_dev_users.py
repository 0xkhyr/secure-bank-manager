#!/usr/bin/env python3
"""
scripts/seed_dev_users.py - create development users (development-only)

Usage:
  python scripts/seed_dev_users.py --force

This script creates demo users (superadmin, admin, operateur) for local development.
It is intentionally gated: either pass --force or set environment variable ALLOW_DEV_USERS=1.
Do NOT run this in production.
"""

import os
import sys
import argparse
from passlib.hash import bcrypt

# Ensure the application path is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db import obtenir_session
from src.models import Utilisateur, RoleUtilisateur

parser = argparse.ArgumentParser(description='Create development users (dev only).')
parser.add_argument('--force', action='store_true', help='Create users even if ALLOW_DEV_USERS is not set')
args = parser.parse_args()

if not args.force and os.getenv('ALLOW_DEV_USERS', '0') not in ('1', 'true', 'True'):
    print("This script is for development only. Set ALLOW_DEV_USERS=1 or use --force to proceed.")
    sys.exit(1)

session = obtenir_session()

try:
    created = []

    def ensure_user(username, password, role):
        existing = session.query(Utilisateur).filter_by(nom_utilisateur=username).first()
        if existing:
            return False
        user = Utilisateur(
            nom_utilisateur=username,
            mot_de_passe_hash=bcrypt.hash(password),
            role=role
        )
        session.add(user)
        return True

    if ensure_user('superadmin', 'superadmin123', RoleUtilisateur.SUPERADMIN):
        created.append('superadmin')
    if ensure_user('admin', 'admin123', RoleUtilisateur.ADMIN):
        created.append('admin')
    if ensure_user('operateur', 'operateur123', RoleUtilisateur.OPERATEUR):
        created.append('operateur')

    if created:
        session.commit()
        print(f"Created demo users: {', '.join(created)} (change their passwords before using outside development)")
    else:
        print("Demo users already exist or were not created.")

except Exception as exc:
    session.rollback()
    print(f"Error creating demo users: {exc}")
    raise
finally:
    session.close()
