import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db
from app.database import init_db, mark_file_processed, save_conjuntura_dados

client = TestClient(app)


@pytest.fixture
def test_db_populated():
    """
    Cria um banco SQLite em memória, simula um documento processado
    e insere um registro de dados operacionais para MRV 3T25.
    """
    conn = init_db(":memory:")

    # Linhagem — catálogo de arquivos processados
    hash_ficticio = "abc123hash"
    caminho_arquivo = "/fixtures/Earnings_Release_3T25.pdf"
    mark_file_processed(conn, hash_ficticio, caminho_arquivo)

    # Dados operacionais — o que a API deve retornar
    save_conjuntura_dados(
        conn=conn,
        empresa="MRV",
        periodo_reportado="3T25",
        vendas_liquidas_r_milhoes=2445.0,
        lancamentos_r_milhoes=2355.0,
        source_file=caminho_arquivo,
        source_hash=hash_ficticio,
    )

    # Injeta o banco de memória na dependência da API
    app.dependency_overrides[get_db] = lambda: conn
    yield conn
    app.dependency_overrides.clear()
    conn.close()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_api_conjuntura_retorna_dados_e_linhagem(test_db_populated):
    """
    GET /api/conjuntura deve retornar 200 com os dados corretos
    e a linhagem (source_file) do PDF que originou o registro.
    """
    response = client.get("/api/conjuntura?empresa=MRV&ano=2025&trimestre=3")

    assert response.status_code == 200, (
        "A rota GET /api/conjuntura deve existir e retornar 200"
    )

    data = response.json()

    # Campos de identificação
    assert "empresa" in data
    assert data["empresa"] == "MRV"
    assert data["ano"] == 2025
    assert data["trimestre"] == 3
    assert data["periodo_reportado"] == "3T25"

    # Linhagem
    assert "source_file" in data, "A resposta deve incluir a linhagem do arquivo (source_file)"
    assert data["source_file"] != "", "source_file não deve estar vazio"

    # Dados operacionais
    assert "dados" in data
    assert data["dados"]["vendas_liquidas_r_milhoes"] == 2445.0
    assert data["dados"]["lancamentos_r_milhoes"] == 2355.0


def test_api_conjuntura_retorna_404_para_empresa_inexistente(test_db_populated):
    """
    Quando não há dados para a empresa/período solicitado,
    a API deve retornar 404 com mensagem explicativa.
    """
    response = client.get("/api/conjuntura?empresa=INEXISTENTE&ano=2025&trimestre=3")
    assert response.status_code == 404


def test_api_list_empresas_retorna_lista(test_db_populated):
    """
    GET /api/conjuntura/empresas deve retornar a lista de empresas disponíveis.
    """
    response = client.get("/api/conjuntura/empresas")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    empresas = [item["empresa"] for item in data]
    assert "MRV" in empresas