import sqlite3
import hashlib
from pathlib import Path

def get_file_hash(filepath: Path | str) -> str:
    """Gera um hash SHA-256 único para o conteúdo do arquivo."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def init_db(db_path="catalogo.db"):
    """Cria a tabela do Catálogo de Dados para controle de idempotência."""
    # check_same_thread=False permite que o FastAPI use o SQLite em suas threads
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_files (
            hash TEXT PRIMARY KEY,
            filename TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def is_file_processed(conn, file_hash: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_files WHERE hash = ?", (file_hash,))
    return cursor.fetchone() is not None

def mark_file_processed(conn, file_hash: str, filename: str):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO processed_files (hash, filename) VALUES (?, ?)", (file_hash, filename))
    conn.commit()