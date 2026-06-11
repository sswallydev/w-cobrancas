from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from app.database import Base


class Cobranca(Base):
    __tablename__ = "cobrancas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_nome = Column(String(120), nullable=False)
    email_cliente = Column(String(120), nullable=False)
    quantidade_boletos = Column(Integer, nullable=False)
    valor_total = Column(Float, nullable=False)
    boletos_resumo = Column(Text, nullable=False)
    arquivos_anexados = Column(Text, nullable=False)
    mensagem_enviada = Column(Text, nullable=True)
    data_envio = Column(DateTime, default=datetime.utcnow)
    cliente_respondeu = Column(Boolean, default=False)
    pagamento_realizado = Column(Boolean, default=False)
    status = Column(String(50), default="pendente")
    observacoes = Column(Text, nullable=True)