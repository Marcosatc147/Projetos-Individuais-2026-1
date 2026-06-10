from pydantic import BaseModel, Field
from typing import List, Optional

class DadosOperacionaisEmpresa(BaseModel):
    nome: str = Field(
        description="O nome oficial ou ticker da empresa de capital aberto (ex: MRV, Tenda, Direcional). Formate sempre em letras MAIÚSCULAS."
    )
    periodo_reportado: str = Field(
        description="O período fiscal principal (trimestre) a que se refere o relatório (ex: '3T25', '1T26', '4T24'). Identifique isso na capa do documento."
    )
    # -----------
    analise_passo_a_passo: str = Field(
        description="Pense em voz alta: Explique como você encontrou os valores nas tabelas analíticas. Se a tabela de Vendas Líquidas estiver 'achatada' (números empilhados de um lado e trimestres de outro), mostre a lógica de pareamento posicional que você usou para chegar ao número exato."
    )
    # -----------
    vendas_liquidas_r_milhoes: Optional[float] = Field(
        default=None,
        description=(
            "O valor absoluto das Vendas Líquidas operacionais em milhões de Reais (R$) REFERENTE APENAS AO PERÍODO REPORTADO NA VARIÁVEL 'periodo_reportado'. "
            "ATENÇÃO - DESAMBIGUAÇÃO CONTÁBIL: Se o documento apresentar duas tabelas/visões diferentes (ex: uma tabela 'Visão Global / 100%' e outra tabela 'Visão % Empresa / %MRV'), "
            "extraia ESTRITAMENTE o valor da visão GLOBAL (100%). "
            "Ignore variações percentuais. O valor deve seguir o padrão internacional (US) para float. "
            "Remova pontos separadores de milhar. (Exemplo: se o documento diz '2.445', retorne '2445.0')."
        )
    )
    lancamentos_r_milhoes: Optional[float] = Field(
        default=None,
        description=(
            "O valor absoluto dos Lançamentos operacionais em milhões de Reais (R$) REFERENTE APENAS AO PERÍODO REPORTADO NA VARIÁVEL 'periodo_reportado'. "
            "ATENÇÃO - DESAMBIGUAÇÃO CONTÁBIL: Se houver a visão 'Global' e a visão '% da Companhia', "
            "priorize ESTRITAMENTE a visão GLOBAL (100%). "
            "Ignore variações percentuais. Formato numérico float internacional (US) sem separador de milhar. (Exemplo: '2.355' vira '2355.0')."
        )
    )

class ConjunturaReport(BaseModel):
    empresas: List[DadosOperacionaisEmpresa] = Field(
        description="Uma lista contendo os dados operacionais financeiros de cada empresa identificada no documento."
    )