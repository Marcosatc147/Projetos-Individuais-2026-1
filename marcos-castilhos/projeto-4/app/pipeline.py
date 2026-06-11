from pathlib import Path

from app.database import (
    init_db,
    get_file_hash,
    is_file_processed,
    mark_file_processed,
    save_conjuntura_dados,
)
from app.extractor import extract_financial_data


def process_document(pdf_path: Path | str, db_conn=None):
    """
    Orquestra a ingestão de um PDF:
      1. Calcula o hash SHA-256 (assinatura única do arquivo).
      2. Verifica idempotência — se já foi processado, retorna 'skipped'.
      3. Aciona o motor UDA (LLM) para extração semântica.
      4. Persiste os dados extraídos no banco (conjuntura_dados).
      5. Registra o hash no catálogo de linhagem (processed_files).
    """
    if db_conn is None:
        db_conn = init_db()

    pdf_path = Path(pdf_path)

    # ── 1. Hash ──────────────────────────────────────────────────────────────
    file_hash = get_file_hash(pdf_path)

    # ── 2. Idempotência ───────────────────────────────────────────────────────
    if is_file_processed(db_conn, file_hash):
        print(
            f"\n[PIPELINE] 🛑 Duplicado! Hash {file_hash[:8]}... já processado. Ignorando."
        )
        return {
            "status": "skipped",
            "reason": "Already processed",
            "hash": file_hash,
        }

    # ── 3. Extração via LLM ───────────────────────────────────────────────────
    print(f"\n[PIPELINE] ✅ Arquivo inédito. Iniciando extração de {pdf_path.name}...")
    report = extract_financial_data(pdf_path)

    # ── 4. Persistência dos dados no banco ────────────────────────────────────
    if report and report.empresas:
        for empresa_data in report.empresas:
            save_conjuntura_dados(
                conn=db_conn,
                empresa=empresa_data.nome,
                periodo_reportado=empresa_data.periodo_reportado,
                vendas_liquidas_r_milhoes=empresa_data.vendas_liquidas_r_milhoes,
                lancamentos_r_milhoes=empresa_data.lancamentos_r_milhoes,
                source_file=str(pdf_path),
                source_hash=file_hash,
            )
            print(
                f"[PIPELINE]    💾 Dados de {empresa_data.nome} "
                f"({empresa_data.periodo_reportado}) salvos no banco."
            )

    # ── 5. Registra no Catálogo de Linhagem ───────────────────────────────────
    mark_file_processed(db_conn, file_hash, str(pdf_path))

    return {
        "status": "success",
        "report": report,
        "hash": file_hash,
    }