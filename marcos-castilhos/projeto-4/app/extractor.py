import os
import instructor
from google import genai
from pathlib import Path
from app.models import ConjunturaReport

def extract_financial_data(pdf_path: Path | str, trimestre_alvo: str = "Trimestre mais recente reportado") -> ConjunturaReport:
    path_str = str(pdf_path)
    if not os.path.exists(path_str):
        raise FileNotFoundError(f"Arquivo não encontrado: {path_str}")

    print(f"[UDA] Enviando PDF para a visão nativa da IA: {Path(path_str).name}...")

    MODELO_LLM = "gemini-3.1-flash-lite" 
    
    # --- SETUP DO CLIENTE ---
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            from kaggle_secrets import UserSecretsClient
            user_secrets = UserSecretsClient()
            api_key = user_secrets.get_secret("GEMINI_API_KEY")
        except Exception:
            pass

    if not api_key:
        raise ValueError("CRITICAL ERROR: Chave GEMINI_API_KEY não encontrada.")

    genai_client = genai.Client(api_key=api_key)
    client = instructor.from_genai(genai_client)

    # --- FASE 1: Upload direto do PDF (Bypass do Docling) ---
    uploaded_pdf = genai_client.files.upload(file=path_str)

    # --- FASE 2: Raciocínio Semântico ---
    prompt = f"""
    Você é um auditor financeiro sênior. Sua tarefa é analisar o documento em PDF anexo usando sua visão computacional e extrair os valores operacionais exatos.

    === COMO DIFERENCIAR MARKETING DE DADOS REAIS ===
    O documento pode ser uma Apresentação de Slides cheia de gráficos e infográficos.
    - FALSO (Marketing): Valores arredondados com letras (ex: "R$ 1,8 BI", "2,0 Bilhões"). É PROIBIDO usar esses.
    - VERDADEIRO (Dado Analítico): Valores com precisão de frações/milhares (ex: "1.128,0", "1.041,4", "1.915,2"). Procure por esses números exatos escondidos dentro de gráficos de barras ou tabelas.

    === DIRETRIZES DE EXTRAÇÃO ===
    1. CONTEXTO TEMPORAL: O alvo da nossa extração é ESTRITAMENTE O {trimestre_alvo.upper()}. 
    2. LEITURA DE IMAGENS E GRÁFICOS: Olhe atentamente para os gráficos de barras e tabelas visuais no PDF. Localize o {trimestre_alvo.upper()} e identifique o número exato associado a ele.
    3. PRECISÃO MATEMÁTICA: Copie o valor exato da imagem/tabela e converta para float americano (ex: de '1.425,0' retorne 1425.0).
    4. NÃO DESISTA: NUNCA retorne valor Nulo (None) se os números decimais exatos estiverem visíveis em qualquer gráfico da construtora.
    """

    report = client.chat.completions.create(
        model=MODELO_LLM, 
        response_model=ConjunturaReport,
        messages=[
            uploaded_pdf,
            {"role": "user", "content": prompt}
        ],
        max_retries=3 
    )

    # Limpeza de memória do servidor do Google
    try:
        uploaded_pdf.delete()
    except Exception:
        pass

    return report