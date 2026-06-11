import time
import pytest
from pathlib import Path
from app.extractor import extract_financial_data
from app.models import ConjunturaReport

FIXTURES_DIR = Path("./tests/fixtures")

DATA_TEST_CASES = [
    (
        "Earnings_Release_3T25.pdf",
        "MRV",
        "3T25",
        2445.0,
        2355.0
    ),
    (
        "Apresentao_de_Resultados_3T25.pdf",
        "CURY",
        "3T25",
        1827.0,
        1986.4
    ),
    (
        "Press-release-Tenda-2025-09-30-mLkphKnR.pdf",
        "TENDA",
        "3T25",
        1232.7,
        1562.9
    )
]

@pytest.mark.parametrize("pdf_name, empresa_nome, periodo_reportado_esperado, esperado_vendas, esperado_lancamentos", DATA_TEST_CASES)
def test_extract_boletim_conjuntura(pdf_name, empresa_nome, periodo_reportado_esperado, esperado_vendas, esperado_lancamentos):
    pdf_path = FIXTURES_DIR / pdf_name
    assert pdf_path.exists(), f"Erro: O arquivo não foi encontrado no caminho absoluto -> {pdf_path.resolve()}"
    
    result: ConjunturaReport = extract_financial_data(
        pdf_path, 
        trimestre_alvo=periodo_reportado_esperado 
    )
    
    assert result is not None, "O motor retornou None"
    empresa_data = next(
    (e for e in result.empresas if empresa_nome.upper() in e.nome.upper()),
    None)
    assert empresa_data is not None, f"Falhou em identificar '{empresa_nome}'"

    assert empresa_data.periodo_reportado == periodo_reportado_esperado, \
        f"Esperado período = {periodo_reportado_esperado}, mas extraiu {empresa_data.periodo_reportado}"

    assert empresa_data.vendas_liquidas_r_milhoes == esperado_vendas, \
        f"Esperado Vendas = {esperado_vendas}, mas extraiu {empresa_data.vendas_liquidas_r_milhoes}"

    assert empresa_data.lancamentos_r_milhoes == esperado_lancamentos, \
        f"Esperado Lançamentos = {esperado_lancamentos}, mas extraiu {empresa_data.lancamentos_r_milhoes}"

    print(f"\n[RATE LIMIT] Teste {empresa_nome} finalizado. Pausando 15s para resfriar a cota gratuita da API...")
    time.sleep(15)