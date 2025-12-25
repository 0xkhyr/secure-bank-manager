#!/bin/bash
# start.sh - Script pour démarrer l'application Flask

# Couleurs pour les messages
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Démarrage de l'application bancaire ===${NC}\n"

# Activer l'environnement virtuel
echo -e "${GREEN}✓${NC} Activation de l'environnement virtuel..."
source .venv/bin/activate

# Exporter les variables d'environnement
export FLASK_APP=src/app.py
export FLASK_ENV=development

# Démarrer Flask
echo -e "${GREEN}✓${NC} Démarrage de Flask sur http://localhost:5000"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

flask run --host=0.0.0.0 --port=5000
