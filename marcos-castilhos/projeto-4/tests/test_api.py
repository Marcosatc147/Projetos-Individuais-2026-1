import pytest
from fastapi.testclient import TestClient
from app.main import app, get_db
from app.database import init_db, mark_file_processed

client = TestClient(app)

@pytest.fixture
def test_db_populated():
    """Cria um banco de dados em memória e simula que um documento já foi processado"""
    conn = init_db(":memory:")
    # Simulando um arquivo processado para termos dados na API
    hash_ficticio = "abc123hash"
    caminho_arquivo = "/kaggle/input/datasets/marcosalt/docs-analise/Earnings_Release_3T25.pdf"
    
    mark_file_processed(conn, hash_ficticio, caminho_arquivo)
    
    # Injetamos a conexão do banco de memória na rota da API
    app.dependency_overrides[get_db] = lambda: conn
    yield conn
    app.dependency_overrides.clear()

def test_api_conjuntura_retorna_dados_e_linhagem(test_db_populated):
    """
    Testa se o endpoint da API retorna os dados formatados
    e a linhagem do arquivo (source_file) com sucesso.
    """
    response = client.get("/api/conjuntura?empresa=MRV&ano=2025&trimestre=3")
    
    assert response.status_code == 200, "A rota GET /api/conjuntura deve existir e retornar 200"
    
    data = response.json()
    assert "empresa" in data
    assert data["empresa"] == "MRV"