import sqlite3
import hashlib
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# HASH
# ---------------------------------------------------------------------------

def get_file_hash(filepath: Path | str) -> str:
    """Gera um hash SHA-256 único para o conteúdo do arquivo."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# INICIALIZAÇÃO
# ---------------------------------------------------------------------------

def init_db(db_path: str = "catalogo.db") -> sqlite3.Connection:
    """
    Cria (ou reabre) o banco SQLite com duas tabelas:
      - processed_files : catálogo de linhagem / idempotência
      - conjuntura_dados: dados operacionais extraídos pelos LLMs
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # acesso por nome de coluna
    cursor = conn.cursor()

    # --- Catálogo de linhagem (idempotência) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            hash         TEXT PRIMARY KEY,
            filename     TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Dados operacionais extraídos ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conjuntura_dados (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa                  TEXT    NOT NULL,
            periodo_reportado        TEXT    NOT NULL,   -- ex: '3T25'
            ano                      INTEGER NOT NULL,   -- ex: 2025
            trimestre                INTEGER NOT NULL,   -- ex: 3
            vendas_liquidas_r_milhoes REAL,
            lancamentos_r_milhoes    REAL,
            source_file              TEXT,               -- linhagem: caminho do PDF
            source_hash              TEXT,               -- linhagem: hash do PDF
            created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(empresa, periodo_reportado)           -- evita duplicatas por período
        )
    """)

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# IDEMPOTÊNCIA
# ---------------------------------------------------------------------------

def is_file_processed(conn: sqlite3.Connection, file_hash: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_files WHERE hash = ?", (file_hash,))
    return cursor.fetchone() is not None


def mark_file_processed(conn: sqlite3.Connection, file_hash: str, filename: str):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO processed_files (hash, filename) VALUES (?, ?)",
        (file_hash, filename),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# PERSISTÊNCIA DOS DADOS EXTRAÍDOS
# ---------------------------------------------------------------------------

def _parse_periodo(periodo: str):
    """
    Converte '3T25' → (ano=2025, trimestre=3).
    Suporta formatos como '3T25', '1T2026', '4T24'.
    Retorna (None, None) se não conseguir parsear.
    """
    try:
        parte_t, parte_ano = periodo.upper().split("T")
        trimestre = int(parte_t)
        ano_raw = int(parte_ano)
        ano = ano_raw + 2000 if ano_raw < 100 else ano_raw
        return ano, trimestre
    except Exception:
        return None, None


def save_conjuntura_dados(
    conn: sqlite3.Connection,
    empresa: str,
    periodo_reportado: str,
    vendas_liquidas_r_milhoes: Optional[float],
    lancamentos_r_milhoes: Optional[float],
    source_file: str,
    source_hash: str,
):
    """
    Persiste (ou atualiza) os dados operacionais de uma empresa/período.
    Usa INSERT OR REPLACE para idempotência a nível de registro.
    """
    ano, trimestre = _parse_periodo(periodo_reportado)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO conjuntura_dados
            (empresa, periodo_reportado, ano, trimestre,
             vendas_liquidas_r_milhoes, lancamentos_r_milhoes,
             source_file, source_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(empresa, periodo_reportado) DO UPDATE SET
            vendas_liquidas_r_milhoes = excluded.vendas_liquidas_r_milhoes,
            lancamentos_r_milhoes     = excluded.lancamentos_r_milhoes,
            source_file               = excluded.source_file,
            source_hash               = excluded.source_hash,
            created_at                = CURRENT_TIMESTAMP
        """,
        (
            empresa.upper(),
            periodo_reportado.upper(),
            ano,
            trimestre,
            vendas_liquidas_r_milhoes,
            lancamentos_r_milhoes,
            source_file,
            source_hash,
        ),
    )
    conn.commit()


def query_conjuntura(
    conn: sqlite3.Connection,
    empresa: str,
    ano: int,
    trimestre: int,
) -> Optional[sqlite3.Row]:
    """
    Retorna a linha de dados para a empresa/ano/trimestre informados, ou None.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM conjuntura_dados
        WHERE empresa = ? AND ano = ? AND trimestre = ?
        LIMIT 1
        """,
        (empresa.upper(), ano, trimestre),
    )
    return cursor.fetchone()