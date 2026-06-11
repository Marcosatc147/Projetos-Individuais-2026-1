"""
scheduler.py — Gatilho de Ingestão Automatizada (Polling / CronJob)
====================================================================

Estratégia: Polling agendado via APScheduler.
  - Varre as páginas de RI das incorporadoras em intervalos configuráveis
    (padrão: a cada 6 horas).
  - Detecta novos links de PDF comparando com os hashes já catalogados.
  - Baixa apenas PDFs inéditos e os envia ao pipeline UDA.
  - Totalmente idempotente: mesmo que o job rode várias vezes, cada PDF
    é processado exatamente uma vez.

Execução manual:
    python -m app.scheduler

Como serviço contínuo (ex: Docker / systemd):
    python -m app.scheduler   # fica em loop; use Ctrl+C para parar
"""

import hashlib
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup

from app.database import init_db, is_file_processed, mark_file_processed
from app.pipeline import process_document

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fontes de dados: portais de RI das incorporadoras
# ---------------------------------------------------------------------------
# Cada entrada define como encontrar PDFs de Prévias/Resultados em cada portal.
# Adicione novas empresas aqui sem alterar nenhum outro arquivo.

RI_SOURCES = [
    {
        "empresa": "MRV",
        "url": "https://ri.mrv.com.br/informacoes-financeiras/central-de-resultados",
        "pdf_keyword": "previa",          # substring no href do link (case-insensitive)
    },
    {
        "empresa": "CURY",
        "url": "https://ri.cury.net/informacoes-aos-investidores/central-de-resultados/",
        "pdf_keyword": "previa",
    },
    {
        "empresa": "TENDA",
        "url": "https://ri.tenda.com/informacoes-financeiras/central-de-resultados",
        "pdf_keyword": "previa",
    },
    {
        "empresa": "DIRECIONAL",
        "url": "https://ri.direcional.com.br/informacoes-financeiras/central-de-resultados/",
        "pdf_keyword": "previa",
    },
    {
        "empresa": "PLANO_E_PLANO",
        "url": "https://ri.planoeplano.com.br/informacoes-financeiras/central-de-resultados/",
        "pdf_keyword": "previa",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_url(url: str) -> str:
    """Gera um hash SHA-256 da URL — usado como assinatura antes do download."""
    return hashlib.sha256(url.encode()).hexdigest()


def _fetch_pdf_links(page_url: str, keyword: str) -> list[str]:
    """
    Faz scraping da página de RI e retorna todos os hrefs que apontam
    para PDFs cujo texto ou URL contém `keyword`.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; UDA-Pipeline/1.0)"}
        resp = httpx.get(page_url, headers=headers, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("Falha ao acessar %s: %s", page_url, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []

    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        text: str = tag.get_text(strip=True).lower()

        if not href.lower().endswith(".pdf"):
            continue
        if keyword.lower() not in href.lower() and keyword.lower() not in text:
            continue

        # Normaliza URL relativa → absoluta
        if href.startswith("http"):
            links.append(href)
        else:
            from urllib.parse import urljoin
            links.append(urljoin(page_url, href))

    return links


def _download_pdf(url: str, dest_dir: Path) -> Optional[Path]:
    """Baixa um PDF para `dest_dir` e retorna o caminho local."""
    filename = url.split("/")[-1].split("?")[0] or "documento.pdf"
    dest_path = dest_dir / filename

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; UDA-Pipeline/1.0)"}
        with httpx.stream("GET", url, headers=headers, timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        return dest_path
    except Exception as exc:
        log.error("Erro ao baixar %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Job principal
# ---------------------------------------------------------------------------

def poll_and_ingest():
    """
    Varre todas as fontes de RI, detecta novos PDFs e os processa.
    Executado pelo APScheduler a cada `POLL_INTERVAL_HOURS` horas.
    """
    log.info("=== [SCHEDULER] Iniciando varredura das fontes de RI ===")
    db_conn = init_db()

    with tempfile.TemporaryDirectory(prefix="uda_pdfs_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for source in RI_SOURCES:
            empresa = source["empresa"]
            url = source["url"]
            keyword = source["pdf_keyword"]

            log.info("[%s] Verificando %s …", empresa, url)
            pdf_links = _fetch_pdf_links(url, keyword)

            if not pdf_links:
                log.info("[%s] Nenhum PDF encontrado.", empresa)
                continue

            log.info("[%s] %d link(s) de PDF encontrado(s).", empresa, len(pdf_links))

            for pdf_url in pdf_links:
                # --- Verificação rápida pela URL (evita download desnecessário) ---
                url_hash = _hash_url(pdf_url)
                if is_file_processed(db_conn, url_hash):
                    log.info("[%s] Já processado (URL hash): %s", empresa, pdf_url)
                    continue

                # --- Download ---
                log.info("[%s] Baixando novo PDF: %s", empresa, pdf_url)
                local_path = _download_pdf(pdf_url, tmp_path)
                if local_path is None:
                    continue

                # --- Processamento (verifica hash do conteúdo também) ---
                result = process_document(local_path, db_conn=db_conn)

                if result["status"] == "success":
                    log.info(
                        "[%s] ✅ Processado com sucesso. Hash: %s",
                        empresa, result["hash"][:8],
                    )
                    # Registra também a URL para não baixar de novo
                    mark_file_processed(db_conn, url_hash, pdf_url)
                elif result["status"] == "skipped":
                    log.info("[%s] ⏩ Conteúdo já processado (hash arquivo).", empresa)
                    mark_file_processed(db_conn, url_hash, pdf_url)

    log.info("=== [SCHEDULER] Varredura concluída ===")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    POLL_INTERVAL_HOURS = int(os.environ.get("POLL_INTERVAL_HOURS", "6"))

    log.info(
        "Scheduler iniciado. Intervalo de polling: %dh. "
        "Primeira execução imediata…",
        POLL_INTERVAL_HOURS,
    )

    # Executa imediatamente ao iniciar, depois a cada N horas
    poll_and_ingest()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        poll_and_ingest,
        trigger="interval",
        hours=POLL_INTERVAL_HOURS,
        id="poll_ri_sources",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler encerrado.")
