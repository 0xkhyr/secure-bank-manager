#!/bin/bash
# rebuild_db.sh - Script pour réinitialiser la base de données

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}⚠️  ATTENTION : Cette action va supprimer toutes les données !${NC}"
read -p "Êtes-vous sûr de vouloir continuer ? (o/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Oo]$ ]]
then
    echo "Annulé."
    exit 1
fi

# Activer l'environnement virtuel si nécessaire ou utiliser le python du venv directement
if [ -d "venv" ]; then
    PYTHON_CMD="venv/bin/python"
elif [ -d ".venv" ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

echo "Utilisation de : $PYTHON_CMD"

# Exécuter la fonction de réinitialisation
PYTHONPATH=. $PYTHON_CMD -c "from src.db import reinitialiser_base_donnees; reinitialiser_base_donnees()"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Base de données reconstruite avec succès.${NC}"
else
    echo -e "${RED}✗ Erreur lors de la reconstruction.${NC}"
fi
