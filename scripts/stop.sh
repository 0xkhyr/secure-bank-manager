#!/bin/bash
# stop.sh - Script pour arrêter l'application Flask

# Couleurs pour les messages
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Arrêt de l'application bancaire ===${NC}\n"

# Trouver et tuer le processus Flask
FLASK_PID=$(ps aux | grep 'flask run' | grep -v grep | awk '{print $2}')

if [ -z "$FLASK_PID" ]; then
    echo -e "${YELLOW}✗ Aucun processus Flask en cours d'exécution${NC}"
else
    echo -e "Arrêt du processus Flask (PID: $FLASK_PID)..."
    kill $FLASK_PID
    echo -e "${RED}✓ Application arrêtée${NC}"
fi

# Arrêter aussi Python si nécessaire
PYTHON_FLASK=$(ps aux | grep 'python.*app.py' | grep -v grep | awk '{print $2}')
if [ ! -z "$PYTHON_FLASK" ]; then
    kill $PYTHON_FLASK
    echo -e "${RED}✓ Processus Python arrêté${NC}"
fi

echo ""
