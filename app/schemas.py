# Este módulo define os modelos de dados utilizados pela API para representar e validar informações relacionadas às cobranças.
# A classe CobrancaResponse estrutura os dados retornados ao usuário, incluindo informações do cliente, boletos, valores, status e histórico de envio.
# A classe AtualizarStatusCobranca permite modificar o andamento de uma cobrança, registrando respostas do cliente, pagamentos e observações.
# Os modelos utilizam Pydantic para garantir a validação automática dos dados recebidos e enviados pela aplicação.
# Essa abordagem contribui para a consistência, segurança e padronização das informações trafegadas pela API.

from datetime import datetime
from pydantic import BaseModel


class CobrancaResponse(BaseModel):
    id: int
    cliente_nome: str
    email_cliente: str
    quantidade_boletos: int
    valor_total: float
    boletos_resumo: str
    arquivos_anexados: str
    mensagem_enviada: str | None
    data_envio: datetime
    cliente_respondeu: bool
    pagamento_realizado: bool
    status: str
    observacoes: str | None

    class Config:
        from_attributes = True


class AtualizarStatusCobranca(BaseModel):
    cliente_respondeu: bool | None = None
    pagamento_realizado: bool | None = None
    status: str | None = None
    observacoes: str | None = None