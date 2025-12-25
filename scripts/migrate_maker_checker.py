import sqlite3
import os
import sys

# Ajouter le chemin du projet pour importer la config si besoin, 
# mais on peut aussi faire simple ici.
db_path = 'data/banque.db'

def migrate():
    print(f"--- Migration de la base de données ({db_path}) ---")
    if not os.path.exists(db_path):
        print(f"✗ Erreur : Base de données introuvable à {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Vérifier si les colonnes existent déjà pour éviter les erreurs
        cursor.execute("PRAGMA table_info(operations_en_attente)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'decision_reason' not in columns:
            print("→ Ajout de la colonne decision_reason...")
            cursor.execute("ALTER TABLE operations_en_attente ADD COLUMN decision_reason VARCHAR(255)")
        else:
            print("✓ La colonne decision_reason existe déjà.")

        if 'decision_comment' not in columns:
            print("→ Ajout de la colonne decision_comment...")
            cursor.execute("ALTER TABLE operations_en_attente ADD COLUMN decision_comment TEXT")
        else:
            print("✓ La colonne decision_comment existe déjà.")

        conn.commit()
        conn.close()
        print("✓ Migration terminée avec succès.")
        
    except Exception as e:
        print(f"✗ Erreur pendant la migration : {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
