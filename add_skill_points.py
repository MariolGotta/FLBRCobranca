"""
Migration: adiciona coluna skill_points na tabela players.
Executar uma vez na VPS:
  python add_skill_points.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'flbr.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Verifica se a coluna já existe
cursor.execute("PRAGMA table_info(players)")
columns = [row[1] for row in cursor.fetchall()]

if 'skill_points' in columns:
    print("Coluna skill_points já existe. Nada a fazer.")
else:
    cursor.execute("ALTER TABLE players ADD COLUMN skill_points INTEGER")
    conn.commit()
    print("Coluna skill_points adicionada com sucesso!")

conn.close()
