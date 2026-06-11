# Esse código gerencia o fluxo de cobranças da API: recebe boletos por upload, salva os arquivos e tenta extrair os dados automaticamente.
# Se a leitura falhar ou faltar nome, valor ou vencimento, ele abre uma pendência para correção manual.
# Quando os dados estão completos, ele gera uma prévia da cobrança e monta o texto do e-mail.
# Após a confirmação, envia o e-mail com os boletos em anexo e registra a cobrança no banco MySQL.
# Também permite listar histórico, consultar cobrança, atualizar status e excluir registros.

import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cobranca
from app.schemas import CobrancaResponse, AtualizarStatusCobranca
from app.constants import STATUS_COBRANCA
from app.services.boleto_ocr_ai_service import analisar_boleto
from app.services.email_service import montar_texto_cobranca, enviar_cobranca_com_anexos


router = APIRouter(
    prefix="/cobrancas",
    tags=["Cobranças"]
)


PREVIEWS_COBRANCA = {}
PENDENCIAS_COBRANCA = {}


class ConfirmarEnvioRequest(BaseModel):
    preview_id: str
    email_cliente: str
    corpo_email: str


class CorrigirBoletoRequest(BaseModel):
    pendencia_id: str
    cliente_nome: str | None = None
    valor: float | None = None
    data_vencimento: str | None = None


@router.post("/preparar")
async def preparar_cobranca(
    arquivos: list[UploadFile] = File(...)
):
    os.makedirs("app/uploads", exist_ok=True)

    boletos_processados = []
    cliente_nome = None
    valor_total = 0

    for arquivo in arquivos:
        nome_arquivo = arquivo.filename
        caminho_arquivo = f"app/uploads/{uuid4()}_{nome_arquivo}"

        conteudo = await arquivo.read()

        with open(caminho_arquivo, "wb") as buffer:
            buffer.write(conteudo)

        try:
            dados = analisar_boleto(caminho_arquivo)
        except Exception as erro:
            pendencia_id = str(uuid4())

            PENDENCIAS_COBRANCA[pendencia_id] = {
                "arquivo_pdf": caminho_arquivo,
                "nome_arquivo": nome_arquivo,
                "dados": {
                    "cliente_nome": None,
                    "valor": None,
                    "data_vencimento": None,
                    "dias_vencidos": None,
                    "status_analise": "nao_identificado",
                    "texto_extraido": str(erro)
                }
            }

            return {
                "precisa_correcao": True,
                "pendencia_id": pendencia_id,
                "arquivo": nome_arquivo,
                "mensagem": "Não foi possível ler o boleto automaticamente.",
                "campos_faltando": [
                    "nome do cliente",
                    "valor",
                    "data de vencimento"
                ],
                "dados_identificados": {
                    "cliente_nome": None,
                    "valor": None,
                    "data_vencimento": None
                },
                "texto_extraido": str(erro)
            }

        campos_faltando = []

        if dados["cliente_nome"] is None:
            campos_faltando.append("nome do cliente")

        if dados["valor"] is None:
            campos_faltando.append("valor")

        if dados["data_vencimento"] is None:
            campos_faltando.append("data de vencimento")

        if campos_faltando:
            pendencia_id = str(uuid4())

            PENDENCIAS_COBRANCA[pendencia_id] = {
                "arquivo_pdf": caminho_arquivo,
                "nome_arquivo": nome_arquivo,
                "dados": dados
            }

            return {
                "precisa_correcao": True,
                "pendencia_id": pendencia_id,
                "arquivo": nome_arquivo,
                "mensagem": "Alguns dados não foram identificados automaticamente.",
                "campos_faltando": campos_faltando,
                "dados_identificados": {
                    "cliente_nome": dados["cliente_nome"],
                    "valor": dados["valor"],
                    "data_vencimento": dados["data_vencimento"]
                },
                "texto_extraido": dados["texto_extraido"]
            }

        if cliente_nome is None:
            cliente_nome = dados["cliente_nome"]

        valor_total += dados["valor"]

        boletos_processados.append({
            "cliente_nome": dados["cliente_nome"],
            "valor": dados["valor"],
            "data_vencimento": dados["data_vencimento"],
            "dias_vencidos": dados["dias_vencidos"],
            "status_analise": dados["status_analise"],
            "arquivo_pdf": caminho_arquivo,
            "nome_arquivo": nome_arquivo
        })

    corpo_email = montar_texto_cobranca(
        cliente_nome=cliente_nome,
        boletos=boletos_processados
    )

    preview_id = str(uuid4())

    PREVIEWS_COBRANCA[preview_id] = {
        "cliente_nome": cliente_nome,
        "valor_total": valor_total,
        "boletos": boletos_processados,
        "corpo_email": corpo_email
    }

    return {
        "precisa_correcao": False,
        "mensagem": "Cobrança preparada com sucesso.",
        "preview_id": preview_id,
        "cliente_nome": cliente_nome,
        "quantidade_boletos": len(boletos_processados),
        "valor_total": valor_total,
        "corpo_email": corpo_email,
        "boletos": [
            {
                "cliente_nome": boleto["cliente_nome"],
                "valor": boleto["valor"],
                "data_vencimento": boleto["data_vencimento"],
                "dias_vencidos": boleto["dias_vencidos"],
                "status_analise": boleto["status_analise"]
            }
            for boleto in boletos_processados
        ]
    }


@router.post("/corrigir-boleto")
def corrigir_boleto_manual(
    dados_corrigidos: CorrigirBoletoRequest
):
    if dados_corrigidos.pendencia_id not in PENDENCIAS_COBRANCA:
        return {
            "erro": "Pendência não encontrada. Envie o boleto novamente."
        }

    pendencia = PENDENCIAS_COBRANCA[dados_corrigidos.pendencia_id]

    dados_originais = pendencia["dados"]

    cliente_nome = (
        dados_corrigidos.cliente_nome
        or dados_originais.get("cliente_nome")
    )

    valor = (
        dados_corrigidos.valor
        or dados_originais.get("valor")
    )

    data_vencimento = (
        dados_corrigidos.data_vencimento
        or dados_originais.get("data_vencimento")
    )

    if isinstance(data_vencimento, str):
        data_vencimento = datetime.strptime(
            data_vencimento,
            "%Y-%m-%d"
        ).date()

    if not cliente_nome or not valor or not data_vencimento:
        return {
            "erro": "Ainda existem campos obrigatórios sem preenchimento.",
            "campos_obrigatorios": [
                "cliente_nome",
                "valor",
                "data_vencimento"
            ]
        }

    dias_vencidos = 0

    hoje = datetime.today().date()

    if data_vencimento < hoje:
        dias_vencidos = (hoje - data_vencimento).days

    status_analise = (
        "vencido"
        if dias_vencidos > 0
        else "em_aberto"
    )

    boleto_corrigido = {
        "cliente_nome": cliente_nome,
        "valor": valor,
        "data_vencimento": data_vencimento,
        "dias_vencidos": dias_vencidos,
        "status_analise": status_analise,
        "arquivo_pdf": pendencia["arquivo_pdf"],
        "nome_arquivo": pendencia["nome_arquivo"]
    }

    corpo_email = montar_texto_cobranca(
        cliente_nome=cliente_nome,
        boletos=[boleto_corrigido]
    )

    preview_id = str(uuid4())

    PREVIEWS_COBRANCA[preview_id] = {
        "cliente_nome": cliente_nome,
        "valor_total": valor,
        "boletos": [boleto_corrigido],
        "corpo_email": corpo_email
    }

    del PENDENCIAS_COBRANCA[dados_corrigidos.pendencia_id]

    return {
        "mensagem": "Dados corrigidos manualmente com sucesso.",
        "preview_id": preview_id,
        "cliente_nome": cliente_nome,
        "quantidade_boletos": 1,
        "valor_total": valor,
        "corpo_email": corpo_email,
        "boletos": [
            {
                "cliente_nome": boleto_corrigido["cliente_nome"],
                "valor": boleto_corrigido["valor"],
                "data_vencimento": boleto_corrigido["data_vencimento"],
                "dias_vencidos": boleto_corrigido["dias_vencidos"],
                "status_analise": boleto_corrigido["status_analise"]
            }
        ]
    }


@router.post("/confirmar-envio")
def confirmar_envio(
    dados: ConfirmarEnvioRequest,
    db: Session = Depends(get_db)
):
    if dados.preview_id not in PREVIEWS_COBRANCA:
        return {
            "erro": "Prévia da cobrança não encontrada. Gere a cobrança novamente."
        }

    preview = PREVIEWS_COBRANCA[dados.preview_id]

    boletos = preview["boletos"]
    cliente_nome = preview["cliente_nome"]
    valor_total = preview["valor_total"]

    enviar_cobranca_com_anexos(
        destinatario=dados.email_cliente,
        assunto="Aviso de cobrança - W Cobranças",
        corpo_email=dados.corpo_email,
        boletos=boletos
    )

    resumo_boletos = ""
    caminhos_anexos = ""

    for boleto in boletos:
        resumo_boletos += (
            f'Boleto de R$ {boleto["valor"]:.2f} '
            f'- vencimento {boleto["data_vencimento"]} '
            f'- dias vencidos {boleto["dias_vencidos"]}\n'
        )

        caminhos_anexos += boleto["arquivo_pdf"] + "\n"

    nova_cobranca = Cobranca(
        cliente_nome=cliente_nome,
        email_cliente=dados.email_cliente,
        quantidade_boletos=len(boletos),
        valor_total=valor_total,
        boletos_resumo=resumo_boletos,
        arquivos_anexados=caminhos_anexos,
        mensagem_enviada=dados.corpo_email,
        status="pendente"
    )

    db.add(nova_cobranca)
    db.commit()
    db.refresh(nova_cobranca)

    del PREVIEWS_COBRANCA[dados.preview_id]

    return {
        "mensagem": "Cobrança enviada com sucesso.",
        "cliente_nome": cliente_nome,
        "email_enviado_para": dados.email_cliente,
        "quantidade_boletos": len(boletos),
        "valor_total": valor_total,
        "status": "pendente"
    }


@router.get("/historico", response_model=list[CobrancaResponse])
def listar_historico(
    db: Session = Depends(get_db)
):
    return (
        db.query(Cobranca)
        .order_by(Cobranca.data_envio.desc())
        .all()
    )


@router.get("/{cobranca_id}", response_model=CobrancaResponse)
def buscar_cobranca(
    cobranca_id: int,
    db: Session = Depends(get_db)
):
    cobranca = (
        db.query(Cobranca)
        .filter(Cobranca.id == cobranca_id)
        .first()
    )

    if not cobranca:
        return {
            "erro": "Cobrança não encontrada."
        }

    return cobranca


@router.patch("/{cobranca_id}/status")
def atualizar_status_cobranca(
    cobranca_id: int,
    dados: AtualizarStatusCobranca,
    db: Session = Depends(get_db)
):
    cobranca = (
        db.query(Cobranca)
        .filter(Cobranca.id == cobranca_id)
        .first()
    )

    if not cobranca:
        return {
            "erro": "Cobrança não encontrada."
        }

    if dados.status:
        if dados.status not in STATUS_COBRANCA:
            return {
                "erro": "Status inválido.",
                "status_permitidos": STATUS_COBRANCA
            }

        cobranca.status = dados.status

    if dados.cliente_respondeu is not None:
        cobranca.cliente_respondeu = dados.cliente_respondeu

    if dados.pagamento_realizado is not None:
        cobranca.pagamento_realizado = dados.pagamento_realizado

    if dados.observacoes is not None:
        cobranca.observacoes = dados.observacoes

    db.commit()
    db.refresh(cobranca)

    return {
        "mensagem": "Status atualizado.",
        "cobranca_id": cobranca.id,
        "novo_status": cobranca.status
    }


@router.delete("/{cobranca_id}")
def excluir_cobranca(
    cobranca_id: int,
    db: Session = Depends(get_db)
):
    cobranca = (
        db.query(Cobranca)
        .filter(Cobranca.id == cobranca_id)
        .first()
    )

    if not cobranca:
        return {
            "erro": "Cobrança não encontrada."
        }

    db.delete(cobranca)
    db.commit()

    return {
        "mensagem": "Cobrança removida do histórico com sucesso.",
        "cobranca_id": cobranca_id
    }