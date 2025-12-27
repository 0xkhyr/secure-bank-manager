#!/usr/bin/env python3
"""Migration helper: add Policy and PolicyHistory tables (dev helper).

For production, use Alembic to generate a proper migration.
"""
from src.db import engine
from src.models import Base, Politique, HistoriquePolitique

if __name__ == '__main__':
    print("Création des tables de politiques si nécessaire...")
    Base.metadata.create_all(engine)
    print("Terminé. Pour la production, préférez une migration Alembic.")
