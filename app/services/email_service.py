# Este módulo gerencia a comunicação automática com os clientes, gerando mensagens de cobrança personalizadas, anexando os boletos correspondentes e realizando o envio por e-mail através de integração SMTP.
# O objetivo é automatizar o processo de cobrança, reduzir atividades manuais e manter um padrão profissional de comunicação.

# Este módulo é responsável por gerar automaticamente o texto das cobranças enviadas aos clientes por e-mail.
# Ele adapta a mensagem conforme a quantidade de boletos, criando textos específicos para um único boleto ou para múltiplos boletos em aberto.
# Também anexa automaticamente os arquivos PDF ou imagens dos boletos à mensagem de cobrança.
# Utiliza um servidor SMTP configurado no sistema para autenticar e realizar o envio dos e-mails.
# Ao final, garante que a cobrança seja enviada com os anexos correspondentes, automatizando o processo de comunicação com o cliente.

import mimetypes
import smtplib
from email.message import EmailMessage

from app.config import settings


def montar_texto_cobranca(cliente_nome: str, boletos: list[dict]) -> str:
    if len(boletos) == 1:
        boleto = boletos[0]

        return f"""Olá, tudo bem?

Aqui é da W Cobranças.

Verificamos em nosso sistema que o cliente {cliente_nome} possui um boleto em aberto no valor de R$ {boleto["valor"]:.2f}, com vencimento em {boleto["data_vencimento"].strftime("%d/%m/%Y")}.

O prazo para pagamento conosco é de até 30 dias após o vencimento. Após esse período, o débito poderá ser encaminhado para tratativas extrajudiciais.

Por gentileza, caso já tenha sido efetuado o pagamento, nos encaminhe o comprovante e desconsidere esta cobrança.

Segue o boleto em anexo.

Atenciosamente,
W Cobranças
"""

    linhas_boletos = ""

    for boleto in boletos:
        linhas_boletos += (
            f'- Boleto no valor de R$ {boleto["valor"]:.2f}, '
            f'vencimento em {boleto["data_vencimento"].strftime("%d/%m/%Y")}\n'
        )

    return f"""Olá, tudo bem?

Aqui é da W Cobranças.

Verificamos em nosso sistema que o cliente {cliente_nome} possui boletos em aberto:

{linhas_boletos}

O prazo para pagamento conosco é de até 30 dias após o vencimento. Após esse período, os débitos poderão ser encaminhados para tratativas extrajudiciais.

Por gentileza, caso já tenha efetuado os pagamentos, nos encaminhe os comprovantes e desconsidere esta cobrança.

Seguem os boletos em anexo.

Atenciosamente,
W Cobranças
"""


def enviar_cobranca_com_anexos(
    destinatario: str,
    assunto: str,
    corpo_email: str,
    boletos: list[dict]
):
    email = EmailMessage()
    email["Subject"] = assunto
    email["From"] = settings.EMAIL_FROM
    email["To"] = destinatario
    email.set_content(corpo_email)

    for boleto in boletos:
        caminho = boleto["arquivo_pdf"]
        nome_arquivo = boleto["nome_arquivo"]

        tipo_mime, _ = mimetypes.guess_type(caminho)

        if tipo_mime:
            maintype, subtype = tipo_mime.split("/")
        else:
            maintype, subtype = "application", "octet-stream"

        with open(caminho, "rb") as arquivo:
            email.add_attachment(
                arquivo.read(),
                maintype=maintype,
                subtype=subtype,
                filename=nome_arquivo
            )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(email)

    return True