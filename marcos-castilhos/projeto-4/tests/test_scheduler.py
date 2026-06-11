"""
test_scheduler.py — Testes de unidade do Scheduler de Polling
=============================================================

Usa mocks para não fazer requisições HTTP reais nem chamar a API do LLM.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from app.database import init_db, is_file_processed
from app.scheduler import _fetch_pdf_links, _hash_url, poll_and_ingest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# _fetch_pdf_links
# ---------------------------------------------------------------------------

def test_fetch_pdf_links_retorna_links_absolutos():
    """
    Dado HTML com links para PDFs que contém a keyword,
    _fetch_pdf_links deve retornar suas URLs absolutas.
    """
    html = """
    <html><body>
      <a href="/docs/previa-3T25.pdf">Prévia 3T25</a>
      <a href="/docs/relatorio-anual.pdf">Relatório Anual</a>
      <a href="https://externa.com/previa-1T26.pdf">Prévia Externa</a>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("app.scheduler.httpx.get", return_value=mock_response):
        links = _fetch_pdf_links("https://ri.empresa.com/resultados", keyword="previa")

    assert len(links) == 2
    assert "https://ri.empresa.com/docs/previa-3T25.pdf" in links
    assert "https://externa.com/previa-1T26.pdf" in links
    # O relatório anual não deve aparecer (não contém keyword)
    assert not any("anual" in l for l in links)


def test_fetch_pdf_links_retorna_vazio_em_falha_de_rede():
    """Se a página não responder, deve retornar lista vazia sem lançar exceção."""
    import httpx

    with patch("app.scheduler.httpx.get", side_effect=httpx.ConnectError("timeout")):
        links = _fetch_pdf_links("https://ri.empresa.com/resultados", keyword="previa")

    assert links == []


# ---------------------------------------------------------------------------
# poll_and_ingest — integração com mocks
# ---------------------------------------------------------------------------

def test_poll_ingest_processa_pdf_novo(test_db, tmp_path):
    """
    Quando um PDF novo é encontrado na página de RI,
    o scheduler deve baixá-lo e chamar process_document.
    """
    fake_pdf = tmp_path / "previa-3T25.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake content")

    pdf_url = "https://ri.mrv.com.br/docs/previa-3T25.pdf"

    with (
        patch("app.scheduler.init_db", return_value=test_db),
        patch("app.scheduler._fetch_pdf_links", return_value=[pdf_url]),
        patch("app.scheduler._download_pdf", return_value=fake_pdf),
        patch("app.scheduler.process_document", return_value={"status": "success", "hash": "aabbcc"}) as mock_process,
        patch("app.scheduler.tempfile.TemporaryDirectory") as mock_tmpdir,
    ):
        mock_tmpdir.return_value.__enter__ = lambda s: str(tmp_path)
        mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

        poll_and_ingest()

    mock_process.assert_called_once()
    called_path = mock_process.call_args[0][0]
    assert called_path == fake_pdf


def test_poll_ingest_nao_reprocessa_url_ja_vista(test_db, tmp_path):
    """
    Se a URL já está no catálogo (via hash da URL),
    o scheduler NÃO deve baixar nem processar novamente.
    """
    from app.database import mark_file_processed

    pdf_url = "https://ri.mrv.com.br/docs/previa-3T25.pdf"
    url_hash = _hash_url(pdf_url)
    mark_file_processed(test_db, url_hash, pdf_url)

    with (
        patch("app.scheduler.init_db", return_value=test_db),
        patch("app.scheduler._fetch_pdf_links", return_value=[pdf_url]),
        patch("app.scheduler._download_pdf") as mock_download,
        patch("app.scheduler.process_document") as mock_process,
        patch("app.scheduler.tempfile.TemporaryDirectory") as mock_tmpdir,
    ):
        mock_tmpdir.return_value.__enter__ = lambda s: str(tmp_path)
        mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

        poll_and_ingest()

    mock_download.assert_not_called()
    mock_process.assert_not_called()
