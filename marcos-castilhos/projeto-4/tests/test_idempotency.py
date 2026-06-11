import pytest
import time
from pathlib import Path
from app.database import init_db
from app.pipeline import process_document

FIXTURES_DIR = Path("./tests/fixtures")

@pytest.fixture
def test_db():
    conn = init_db(":memory:")
    yield conn
    conn.close()

def test_idempotency_avoids_duplicate_processing(test_db):
    pdf_path = FIXTURES_DIR / "Earnings_Release_3T25.pdf"
    
    # Primeira chamada: o documento é novo, deve ir para a IA e ter sucesso
    result1 = process_document(pdf_path, db_conn=test_db)
    assert result1["status"] == "success", "A primeira extração deveria ter sucesso."
    assert result1["report"] is not None
    
    # Segunda chamada: o documento já foi lido, deve pular
    result2 = process_document(pdf_path, db_conn=test_db)
    assert result2["status"] == "skipped", "O sistema não reconheceu o PDF repetido."
    assert result2["reason"] == "Already processed"
    
    print("\n[RATE LIMIT] Teste de Idempotência finalizado. Pausando 20s para esfriar a API antes do próximo teste...")
    time.sleep(20)