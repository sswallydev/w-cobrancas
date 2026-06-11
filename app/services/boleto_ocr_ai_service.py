# Este módulo utiliza OCR e regras de inteligência baseada em confiança para extrair automaticamente informações de boletos e faturas.
# O sistema identifica nome do cliente, valor e vencimento, valida a qualidade dos dados encontrados e solicita correção manual quando necessário, garantindo maior precisão no processo de cobrança automatizada.

# Ele recebe PDFs ou imagens, converte o conteúdo em texto usando OCR (Tesseract) e prepara o texto para análise.
# Utiliza regras, regex e pontuações de confiança para identificar automaticamente o nome do cliente, valor do boleto e data de vencimento.
# Compara vários candidatos encontrados no documento e escolhe os dados mais prováveis, evitando confundir informações como limite de crédito, data de emissão e taxas.
# Calcula se o boleto está vencido, quantos dias está em atraso e gera uma pontuação geral de confiabilidade da análise.
# Caso a confiança seja baixa, devolve os campos não identificados para que o usuário possa corrigir manualmente antes de gerar e enviar a cobrança.

import os
import re
from datetime import datetime, date

import pytesseract
from pdf2image import convert_from_path
from PIL import Image


pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\Users\Wallysson\Downloads\poppler-26.02.0\Library\bin"


def validar_dependencias():
    if not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
        raise Exception(f"Tesseract não encontrado em: {pytesseract.pytesseract.tesseract_cmd}")

    if not os.path.exists(POPPLER_PATH):
        raise Exception(f"Poppler não encontrado em: {POPPLER_PATH}")


def extrair_texto_arquivo(caminho_arquivo: str) -> str:
    validar_dependencias()

    if caminho_arquivo.lower().endswith(".pdf"):
        paginas = convert_from_path(
            caminho_arquivo,
            dpi=300,
            poppler_path=POPPLER_PATH
        )

        texto_final = ""

        for pagina in paginas:
            texto_final += pytesseract.image_to_string(
                pagina,
                lang="por"
            ) + "\n"

        return texto_final

    imagem = Image.open(caminho_arquivo)

    return pytesseract.image_to_string(
        imagem,
        lang="por"
    )


def limpar_texto(texto: str) -> str:
    texto = texto.replace("\n", " ")
    texto = texto.replace("|", " | ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_linhas(texto: str) -> list[str]:
    linhas = texto.splitlines()
    return [re.sub(r"\s+", " ", linha).strip() for linha in linhas if linha.strip()]


def converter_valor_brasileiro(valor_texto: str) -> float:
    valor_texto = valor_texto.replace("R$", "").strip()

    if re.match(r"^\d+\.\d{2}$", valor_texto):
        return float(valor_texto)

    valor_texto = valor_texto.replace(".", "")
    valor_texto = valor_texto.replace(",", ".")

    return float(valor_texto)


def data_valida(data_texto: str) -> date | None:
    try:
        return datetime.strptime(data_texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def limpar_nome_cliente(nome: str) -> str:
    nome = re.sub(r"\bCPF\b.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\bCNPJ\b.*", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\|.*", "", nome)
    nome = re.sub(r"\d+", "", nome)
    nome = re.sub(r"[^\wÀ-ÿ\s]", " ", nome)
    nome = re.sub(r"\s+", " ", nome)

    return nome.strip()


def nome_valido(nome: str) -> bool:
    termos_invalidos = [
        "BANCO",
        "BANK",
        "MASTERCARD",
        "VISA",
        "VIVO",
        "TELEFONICA",
        "TELEFÔNICA",
        "ULTRAGAZ",
        "FATURA",
        "VALOR",
        "VENCIMENTO",
        "PAGAMENTO",
        "CNPJ",
        "CPF",
        "ENDERECO",
        "ENDEREÇO",
        "RUA",
        "AVENIDA",
        "RESUMO",
        "LIMITE",
        "CRÉDITO",
        "CREDITO",
        "TOTAL",
        "AGÊNCIA",
        "AGENCIA",
        "BENEFICIÁRIO",
        "BENEFICIARIO",
        "MÊS",
        "MES",
        "REFERÊNCIA",
        "REFERENCIA",
        "DEMONSTRATIVO",
        "DESPESAS",
        "CONSUMO",
        "DADOS",
        "ESTABELECIMENTO",
        "FATURAMENTO",
        "AUTENTICAÇÃO",
        "MECÂNICA"
    ]

    nome_upper = nome.upper()

    if any(termo in nome_upper for termo in termos_invalidos):
        return False

    if len(nome.split()) < 2:
        return False

    if len(nome) < 6:
        return False

    return True


def adicionar_candidato_nome(candidatos: list[dict], nome: str, score: int, origem: str):
    nome = limpar_nome_cliente(nome)

    if nome_valido(nome):
        candidatos.append({
            "valor": nome[:120],
            "score": score,
            "origem": origem
        })


def extrair_nome_cliente_com_confianca(texto: str) -> tuple[str | None, int, list[dict]]:
    texto_limpo = limpar_texto(texto)
    linhas = normalizar_linhas(texto)

    candidatos = []

    padroes = [
        {
            "regex": r"Dados\s+do\s+Estabelecimento\s+([A-Za-zÀ-ÿ\s]{6,120})\s+Aviso",
            "score": 99,
            "origem": "dados do estabelecimento"
        },
        {
            "regex": r"Dados\s+do\s+Faturamento\s+([A-Za-zÀ-ÿ\s]{6,120})\s+\d",
            "score": 98,
            "origem": "dados do faturamento"
        },
        {
            "regex": r"Código\s+Cliente:\s*\d+\s+([A-Za-zÀ-ÿ\s]{6,120})\s+R\s+",
            "score": 95,
            "origem": "nome após código cliente"
        },
        {
            "regex": r"([A-Za-zÀ-ÿ\s]{6,120})\s*\|\s*CPF\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
            "score": 92,
            "origem": "nome antes de CPF"
        },
        {
            "regex": r"([A-Za-zÀ-ÿ\s]{6,120})\s+CPF\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
            "score": 90,
            "origem": "nome antes de CPF sem separador"
        },
        {
            "regex": r"Pagador\s*[:\-]?\s*([A-Za-zÀ-ÿ\s]{6,120})\s+(CPF|CNPJ|Endereço|Endereco)",
            "score": 90,
            "origem": "pagador"
        },
        {
            "regex": r"Sacado\s*[:\-]?\s*([A-Za-zÀ-ÿ\s]{6,120})\s+(CPF|CNPJ|Endereço|Endereco)",
            "score": 90,
            "origem": "sacado"
        },
        {
            "regex": r"Cliente\s*[:\-]?\s*([A-Za-zÀ-ÿ\s]{6,120})\s+(CPF|CNPJ|Endereço|Endereco)",
            "score": 88,
            "origem": "cliente"
        },
        {
            "regex": r"ESTUDANTE\s+CURSO.*?\d{4}\.\d{2}\.\d{5}-\d\s+([A-Za-zÀ-ÿ\s]+?)\s+ANO",
            "score": 92,
            "origem": "boleto educacional"
        },
        {
            "regex": r"Olá,\s*([A-Za-zÀ-ÿ\s]{2,60})[!\.,]",
            "score": 65,
            "origem": "saudação"
        }
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao["regex"],
            texto_limpo,
            re.IGNORECASE
        )

        if resultado:
            adicionar_candidato_nome(
                candidatos,
                resultado.group(1),
                padrao["score"],
                padrao["origem"]
            )

    for index, linha in enumerate(linhas):
        linha_upper = linha.upper()

        if "DADOS DO ESTABELECIMENTO" in linha_upper or "DADOS DO FATURAMENTO" in linha_upper:
            proximas_linhas = linhas[index + 1:index + 4]

            for proxima in proximas_linhas:
                adicionar_candidato_nome(
                    candidatos,
                    proxima,
                    86,
                    "linha próxima de dados do cliente"
                )

        if re.match(r"^[A-ZÀ-Ÿ\s]{8,80}$", linha):
            adicionar_candidato_nome(
                candidatos,
                linha,
                70,
                "linha em caixa alta"
            )

    if not candidatos:
        return None, 0, []

    candidatos.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    melhor = candidatos[0]

    return melhor["valor"], melhor["score"], candidatos


def contexto_tem_data_nao_vencimento(contexto: str) -> bool:
    termos_bloqueio = [
        "EMISSÃO",
        "EMISSAO",
        "DT. DE EMISSÃO",
        "DT DE EMISSÃO",
        "DATA DO DOCUMENTO",
        "DATA PROCESSAMENTO",
        "PROCESSAMENTO",
        "DOCUMENTO",
        "FECHAMENTO",
        "REFERÊNCIA",
        "REFERENCIA",
        "MÊS REFERÊNCIA",
        "MES REFERENCIA",
        "HISTÓRICO",
        "HISTORICO",
        "LEITURA",
        "CONSUMO",
        "DATA INICIAL",
        "DATA FINAL",
        "APURAÇÃO",
        "APURACAO",
        "PERÍODO",
        "PERIODO"
    ]

    contexto_upper = contexto.upper()

    return any(termo in contexto_upper for termo in termos_bloqueio)


def adicionar_candidato_data(candidatos: list[dict], data_texto: str, score: int, origem: str):
    data = data_valida(data_texto)

    if data:
        candidatos.append({
            "valor": data,
            "score": score,
            "origem": origem
        })


def extrair_vencimento_com_confianca(texto: str) -> tuple[date | None, int, list[dict]]:
    texto_limpo = limpar_texto(texto)
    candidatos = []

    padroes = [
        {
            "regex": r"Dt\.?\s*de\s*Emissão\s+Mês\s+de\s+Referência\s+Vencimento\s+Valor\s+Total\s+a\s+Pagar\s*\(R\$\)\s+\d{2}/\d{2}/\d{4}\s+\d{2}/\d{4}\s+(\d{2}/\d{2}/\d{4})",
            "score": 99,
            "origem": "tabela emissão/referência/vencimento/valor"
        },
        {
            "regex": r"Demonstrativo\s+Nro\..*?Mês\s+de\s+Referência\s+Vencimento.*?\d{2}/\d{2}/\d{4}\s+\d{2}/\d{4}\s+(\d{2}/\d{2}/\d{4})",
            "score": 98,
            "origem": "demonstrativo com vencimento"
        },
        {
            "regex": r"VENCIMENTO\s+VALOR\s+A\s+PAGAR\s*\(R\$\)\s*(\d{2}/\d{2}/\d{4})",
            "score": 98,
            "origem": "vivo cabeçalho vencimento valor"
        },
        {
            "regex": r"Data\s+de\s+vencimento\s+da\s+fatura\s+(\d{2}/\d{2}/\d{4})",
            "score": 98,
            "origem": "data de vencimento da fatura"
        },
        {
            "regex": r"Vencimento\s+do\s+boleto:\s*(\d{2}/\d{2}/\d{4})",
            "score": 98,
            "origem": "vencimento do boleto"
        },
        {
            "regex": r"Com\s+vencimento\s+em\s*(\d{2}/\d{2}/\d{4})",
            "score": 95,
            "origem": "com vencimento em"
        },
        {
            "regex": r"Vencimento\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
            "score": 90,
            "origem": "vencimento direto"
        }
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao["regex"],
            texto_limpo,
            re.IGNORECASE
        )

        if resultado:
            adicionar_candidato_data(
                candidatos,
                resultado.group(1),
                padrao["score"],
                padrao["origem"]
            )

    ocorrencias_datas = list(
        re.finditer(
            r"\d{2}/\d{2}/\d{4}",
            texto_limpo
        )
    )

    for ocorrencia in ocorrencias_datas:
        data_texto = ocorrencia.group()

        inicio = max(0, ocorrencia.start() - 100)
        fim = min(len(texto_limpo), ocorrencia.end() + 100)

        contexto = texto_limpo[inicio:fim]
        contexto_upper = contexto.upper()

        if contexto_tem_data_nao_vencimento(contexto):
            continue

        score = 10

        if "VENCIMENTO" in contexto_upper:
            score += 40

        if "PAGAR" in contexto_upper:
            score += 20

        if "VALOR" in contexto_upper:
            score += 10

        if "BOLETO" in contexto_upper:
            score += 5

        adicionar_candidato_data(
            candidatos,
            data_texto,
            score,
            "data por contexto"
        )

    if not candidatos:
        return None, 0, []

    candidatos.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    melhor = candidatos[0]

    return melhor["valor"], melhor["score"], candidatos


def adicionar_candidato_valor(candidatos: list[dict], valor_texto: str, score: int, origem: str):
    try:
        valor = converter_valor_brasileiro(valor_texto)

        if valor > 1:
            candidatos.append({
                "valor": valor,
                "score": score,
                "origem": origem
            })

    except Exception:
        pass


def extrair_valor_com_confianca(texto: str, data_vencimento: date | None = None) -> tuple[float | None, int, list[dict]]:
    texto_limpo = limpar_texto(texto)
    candidatos = []

    valor_regex = r"(\d+(?:[\.,]\d{2}))"

    padroes = [
        {
            "regex": rf"PAGAMENTO\s+AT[ÉE]\s+O\s+VENCIMENTO.*?R\$\s*{valor_regex}",
            "score": 115,
            "origem": "pagamento até o vencimento"
        },
        {
            "regex": rf"TOTAL\s+A\s+PAGAR\s+R\$\s*{valor_regex}",
            "score": 112,
            "origem": "total a pagar direto"
        },
        {
            "regex": rf"No\s+vencimento.*?TOTAL\s+A\s+PAGAR\s+R\$\s*{valor_regex}",
            "score": 112,
            "origem": "total a pagar no vencimento"
        },
        {
            "regex": rf"Valor\s+Cobrado\s+R\$\s*{valor_regex}",
            "score": 108,
            "origem": "valor cobrado"
        },
        {
            "regex": rf"Valor\s+total\s+da\s+fatura\s+R\$\s*{valor_regex}",
            "score": 105,
            "origem": "valor total da fatura"
        },
        {
            "regex": rf"Valor\s+total\s+do\s+boleto:\s*R\$\s*{valor_regex}",
            "score": 105,
            "origem": "valor total do boleto"
        },
        {
            "regex": rf"Valor\s+da\s+fatura\s+R\$\s*{valor_regex}",
            "score": 102,
            "origem": "valor da fatura"
        },
        {
            "regex": rf"O\s+valor\s+total\s+a\s+pagar\s+[ée]:?\s*R\$\s*{valor_regex}",
            "score": 100,
            "origem": "valor total a pagar"
        },
        {
            "regex": rf"Dt\.?\s*de\s*Emissão\s+Mês\s+de\s+Referência\s+Vencimento\s+Valor\s+Total\s+a\s+Pagar\s*\(R\$\)\s+\d{{2}}/\d{{2}}/\d{{4}}\s+\d{{2}}/\d{{4}}\s+\d{{2}}/\d{{2}}/\d{{4}}\s+{valor_regex}",
            "score": 110,
            "origem": "tabela emissão/referência/vencimento/valor"
        },
        {
            "regex": rf"VENCIMENTO\s+VALOR\s+A\s+PAGAR\s*\(R\$\)\s*\d{{2}}/\d{{2}}/\d{{4}}\s*{valor_regex}",
            "score": 106,
            "origem": "vivo cabeçalho vencimento valor"
        },
        {
            "regex": rf"Total\s+do\s+Faturamento\s+{valor_regex}",
            "score": 96,
            "origem": "total do faturamento"
        },
        {
            "regex": rf"Data\s+Descrição\s+Valor\s*\(R\$\).*?{valor_regex}",
            "score": 92,
            "origem": "dados do faturamento"
        },
        {
            "regex": rf"GLP\s+GRANEL\s+-\s+PTP\s*\|?\s*{valor_regex}",
            "score": 90,
            "origem": "item glp granel"
        }
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao["regex"],
            texto_limpo,
            re.IGNORECASE
        )

        if resultado:
            adicionar_candidato_valor(
                candidatos,
                resultado.group(1),
                padrao["score"],
                padrao["origem"]
            )

    ocorrencias = list(
        re.finditer(
            rf"R\$\s*{valor_regex}",
            texto_limpo
        )
    )

    for ocorrencia in ocorrencias:
        inicio = max(0, ocorrencia.start() - 140)
        fim = min(len(texto_limpo), ocorrencia.end() + 140)

        contexto = texto_limpo[inicio:fim].upper()

        score = 30

        if "PAGAMENTO ATÉ O VENCIMENTO" in contexto or "PAGAMENTO ATE O VENCIMENTO" in contexto:
            score += 85

        if "TOTAL A PAGAR" in contexto:
            score += 75

        if "NO VENCIMENTO" in contexto:
            score += 60

        if "VALOR COBRADO" in contexto:
            score += 60

        if "VALOR TOTAL DA FATURA" in contexto:
            score += 70

        if "VALOR TOTAL DO BOLETO" in contexto:
            score += 70

        if "VALOR DA FATURA" in contexto:
            score += 60

        if "VALOR DO DOCUMENTO" in contexto:
            score -= 20

        if "APÓS O VENCIMENTO" in contexto or "APOS O VENCIMENTO" in contexto:
            score -= 35

        if "LIMITE" in contexto and "CRÉDITO" in contexto:
            score -= 140

        if "MULTA" in contexto:
            score -= 40

        if "JUROS" in contexto:
            score -= 40

        if "TAXA" in contexto:
            score -= 35

        if "IOF" in contexto:
            score -= 35

        if "ENTRADA" in contexto:
            score -= 35

        if "PARCELAMENTO" in contexto:
            score -= 35

        adicionar_candidato_valor(
            candidatos,
            ocorrencia.group(1),
            score,
            "valor com R$ por contexto"
        )

    if not candidatos:
        return None, 0, []

    candidatos.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    melhor = candidatos[0]

    if melhor["score"] < 75:
        return None, melhor["score"], candidatos

    return melhor["valor"], melhor["score"], candidatos


def calcular_dias_vencidos(data_vencimento: date) -> int:
    hoje = date.today()

    if data_vencimento < hoje:
        return (hoje - data_vencimento).days

    return 0


def calcular_confianca_geral(
    score_nome: int,
    score_valor: int,
    score_vencimento: int
) -> int:
    if score_nome == 0 or score_valor == 0 or score_vencimento == 0:
        return 0

    return int(
        (score_nome + score_valor + score_vencimento) / 3
    )


def analisar_boleto(caminho_arquivo: str) -> dict:
    texto = extrair_texto_arquivo(caminho_arquivo)

    vencimento, score_vencimento, candidatos_vencimento = extrair_vencimento_com_confianca(texto)

    valor, score_valor, candidatos_valor = extrair_valor_com_confianca(
        texto,
        vencimento
    )

    nome, score_nome, candidatos_nome = extrair_nome_cliente_com_confianca(texto)

    confianca_geral = calcular_confianca_geral(
        score_nome,
        score_valor,
        score_vencimento
    )

    dias_vencidos = (
        calcular_dias_vencidos(vencimento)
        if vencimento
        else None
    )

    status = (
        "vencido"
        if dias_vencidos and dias_vencidos > 0
        else "em_aberto"
    )

    LIMITE_CONFIANCA = 75

    if confianca_geral < LIMITE_CONFIANCA:
        if score_nome < 75:
            nome = None

        if score_valor < 75:
            valor = None

        if score_vencimento < 75:
            vencimento = None
            dias_vencidos = None

    return {
        "cliente_nome": nome,
        "valor": valor,
        "data_vencimento": vencimento,
        "dias_vencidos": dias_vencidos,
        "status_analise": status,
        "confianca_geral": confianca_geral,
        "score_nome": score_nome,
        "score_valor": score_valor,
        "score_vencimento": score_vencimento,
        "candidatos_nome": candidatos_nome[:5],
        "candidatos_valor": candidatos_valor[:5],
        "candidatos_vencimento": candidatos_vencimento[:5],
        "texto_extraido": limpar_texto(texto)[:2500]
    }