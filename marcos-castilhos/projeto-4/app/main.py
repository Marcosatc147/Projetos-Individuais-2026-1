import sqlite3
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db, query_conjuntura

app = FastAPI(
    title="API Conjuntura Habitacional",
    description="Serve os dados operacionais das incorporadoras extraídos pelo pipeline UDA.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Injeção de Dependência — permite mock nos testes
# ---------------------------------------------------------------------------

def get_db():
    conn = init_db()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/conjuntura")
def get_conjuntura(
    empresa: str,
    ano: int,
    trimestre: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Retorna os dados operacionais e a linhagem do arquivo-fonte.

    Exemplo: GET /api/conjuntura?empresa=MRV&ano=2025&trimestre=3
    """
    row = query_conjuntura(db, empresa=empresa, ano=ano, trimestre=trimestre)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Nenhum dado encontrado para empresa='{empresa.upper()}', "
                f"ano={ano}, trimestre={trimestre}. "
                "Verifique se o pipeline já processou o PDF correspondente."
            ),
        )

    return {
        "empresa": row["empresa"],
        "periodo_reportado": row["periodo_reportado"],
        "ano": row["ano"],
        "trimestre": row["trimestre"],
        "source_file": row["source_file"],
        "source_hash": row["source_hash"],
        "dados": {
            "vendas_liquidas_r_milhoes": row["vendas_liquidas_r_milhoes"],
            "lancamentos_r_milhoes": row["lancamentos_r_milhoes"],
        },
    }

@app.get("/api/pipeline/status")
def get_pipeline_status(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "SELECT filename, hash, processed_at FROM processed_files ORDER BY processed_at DESC"
    )
    rows = cursor.fetchall()
    return [
        {"filename": r["filename"], "hash": r["hash"], "processed_at": r["processed_at"]}
        for r in rows
    ]

@app.get("/api/conjuntura/empresas")
def list_empresas(db: sqlite3.Connection = Depends(get_db)):
    """Lista todas as empresas e períodos disponíveis no banco."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT DISTINCT empresa, periodo_reportado, ano, trimestre "
        "FROM conjuntura_dados ORDER BY empresa, ano, trimestre"
    )
    rows = cursor.fetchall()
    return [
        {
            "empresa": r["empresa"],
            "periodo_reportado": r["periodo_reportado"],
            "ano": r["ano"],
            "trimestre": r["trimestre"],
        }
        for r in rows
    ]

app.mount("/static", StaticFiles(directory="app/static"), name="static")

if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/")
    def root():
        return FileResponse("app/static/index.html")

