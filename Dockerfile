# Utiliser Python 3.11 slim pour une image légère
FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier les dépendances
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Créer le répertoire data s'il n'existe pas
RUN mkdir -p /app/data

# Exposer le port 5000
EXPOSE 5000

# Variables d'environnement par défaut
ENV FLASK_APP=src/app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Lancer l'application avec Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--chdir", "/app", "src.app:app"]
