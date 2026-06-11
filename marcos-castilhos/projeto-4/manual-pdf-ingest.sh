python -c "
from app.pipeline import process_document
from app.database import init_db

conn = init_db()
result = process_document('./tests/fixtures/Press-release-Tenda-2025-09-30-mLkphKnR.pdf', db_conn=conn)
print(result['status'])
"