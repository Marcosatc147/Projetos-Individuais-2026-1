from pathlib import Path
from app.database import init_db, get_file_hash, is_file_processed, mark_file_processed
from app.extractor import extract_financial_data

def process_document(pdf_path: Path | str, db_conn=None):
    """
    Orquestra a ingestão: Verifica idempotência e só aciona a IA se o arquivo for inédito.
    """
    if db_conn is None:
        db_conn = init_db()
        
    # 1. Gera o Hash
    file_hash = get_file_hash(pdf_path)
    
    # 2. Verifica Idempotência
    if is_file_processed(db_conn, file_hash):
        print(f"\n[PIPELINE] 🛑 Arquivo duplicado detectado! Hash {file_hash[:8]}... já processado. Ignorando.")
        return {
            "status": "skipped", 
            "reason": "Already processed", 
            "hash": file_hash
        }
        
    # Faz o processamento com IA (Restaurando a variável report)
    print(f"\n[PIPELINE] ✅ Arquivo inédito. Iniciando extração de {Path(pdf_path).name}...")
    report = extract_financial_data(pdf_path)
    
    # Registra no Catálogo de Dados
    mark_file_processed(db_conn, file_hash, str(pdf_path))
    
    return {
        "status": "success", 
        "report": report, 
        "hash": file_hash
    }