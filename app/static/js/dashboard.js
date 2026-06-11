const form = document.getElementById("form-cobranca");
const resultado = document.getElementById("resultado");
const historico = document.getElementById("historico");

let previewIdAtual = null;
let emailClienteAtual = null;
let pendenciaIdAtual = null;

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    resultado.className = "";
    resultado.innerHTML = "Analisando boleto e preparando cobrança...";

    const formData = new FormData(form);
    emailClienteAtual = formData.get("email_cliente");

    try {
        const response = await fetch("/cobrancas/preparar", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (
            data.precisa_correcao ||
            data.erro ||
            !data.preview_id ||
            !data.cliente_nome ||
            !data.valor_total ||
            !data.corpo_email
        ) {
            pendenciaIdAtual = data.pendencia_id;
            mostrarFormularioCorrecao(data);
            return;
        }

        mostrarPreviaCobranca(data);

    } catch (error) {
        console.error(error);
        resultado.className = "erro";
        resultado.innerHTML = "Erro ao preparar cobrança.";
    }
});

function mostrarFormularioCorrecao(data) {
    resultado.className = "erro";

    const identificados = data.dados_identificados || {};

    const nome = identificados.cliente_nome || "";
    const valor = identificados.valor || "";
    const vencimento = identificados.data_vencimento || "";

    resultado.innerHTML = `
        <h3>Preenchimento manual necessário</h3>

        <p>
            O OCR não conseguiu identificar todos os dados do boleto.
            Preencha os dados abaixo para gerar a cobrança normalmente.
        </p>

        <p>
            <strong>Arquivo:</strong> ${data.arquivo || "boleto enviado"}
        </p>

        <div class="manual-form">
            <label>Nome do cliente</label>
            <input
                type="text"
                id="manual-cliente-nome"
                value="${nome}"
                placeholder="Ex: Carolina Dias Barreto"
            >

            <label>Valor do boleto</label>
            <input
                type="number"
                step="0.01"
                id="manual-valor"
                value="${valor}"
                placeholder="Ex: 126.21"
            >

            <label>Data de vencimento</label>
            <input
                type="date"
                id="manual-data-vencimento"
                value="${vencimento}"
            >

            <button
                type="button"
                class="btn-confirmar"
                onclick="corrigirBoletoManual()"
            >
                Gerar prévia da cobrança
            </button>
        </div>
    `;
}

async function corrigirBoletoManual() {
    const clienteNome = document.getElementById("manual-cliente-nome").value;
    const valor = document.getElementById("manual-valor").value;
    const dataVencimento = document.getElementById("manual-data-vencimento").value;

    if (!clienteNome || !valor || !dataVencimento) {
        resultado.className = "erro";
        resultado.innerHTML += `
            <p><strong>Preencha nome, valor e vencimento para continuar.</strong></p>
        `;
        return;
    }

    resultado.className = "";
    resultado.innerHTML = "Gerando prévia com dados manuais...";

    try {
        const response = await fetch("/cobrancas/corrigir-boleto", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                pendencia_id: pendenciaIdAtual,
                cliente_nome: clienteNome,
                valor: Number(valor),
                data_vencimento: dataVencimento
            })
        });

        const data = await response.json();

        if (data.erro) {
            resultado.className = "erro";
            resultado.innerHTML = `<strong>Erro:</strong> ${data.erro}`;
            return;
        }

        mostrarPreviaCobranca(data);

    } catch (error) {
        console.error(error);
        resultado.className = "erro";
        resultado.innerHTML = "Erro ao gerar prévia manual.";
    }
}

function mostrarPreviaCobranca(data) {
    previewIdAtual = data.preview_id;

    resultado.className = "sucesso";

    resultado.innerHTML = `
        <h3>Prévia da cobrança</h3>

        <p><strong>Cliente:</strong> ${data.cliente_nome}</p>
        <p><strong>Quantidade de boletos:</strong> ${data.quantidade_boletos}</p>
        <p><strong>Valor total:</strong> R$ ${formatarMoeda(data.valor_total)}</p>

        <hr>

        <label><strong>Texto do e-mail</strong></label>

        <textarea id="corpo-email" rows="12">${data.corpo_email}</textarea>

        <br><br>

        <button type="button" class="btn-confirmar" onclick="confirmarEnvio()">
            Confirmar envio
        </button>
    `;
}

async function confirmarEnvio() {
    const corpoEmail = document.getElementById("corpo-email").value;

    resultado.className = "";
    resultado.innerHTML = "Enviando cobrança...";

    try {
        const response = await fetch("/cobrancas/confirmar-envio", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                preview_id: previewIdAtual,
                email_cliente: emailClienteAtual,
                corpo_email: corpoEmail
            })
        });

        const data = await response.json();

        if (data.erro) {
            resultado.className = "erro";
            resultado.innerHTML = `<strong>Erro:</strong> ${data.erro}`;
            return;
        }

        resultado.className = "sucesso";

        resultado.innerHTML = `
            <h3>Cobrança enviada com sucesso</h3>
            <p><strong>Cliente:</strong> ${data.cliente_nome}</p>
            <p><strong>E-mail:</strong> ${data.email_enviado_para}</p>
            <p><strong>Quantidade de boletos:</strong> ${data.quantidade_boletos}</p>
            <p><strong>Valor total:</strong> R$ ${formatarMoeda(data.valor_total)}</p>
        `;

        form.reset();
        previewIdAtual = null;
        pendenciaIdAtual = null;
        emailClienteAtual = null;

        carregarHistorico();

    } catch (error) {
        console.error(error);
        resultado.className = "erro";
        resultado.innerHTML = "Erro ao enviar cobrança.";
    }
}

function formatarMoeda(valor) {
    return Number(valor).toFixed(2).replace(".", ",");
}

function formatarData(dataIso) {
    if (!dataIso) return "-";

    const data = new Date(dataIso);

    return (
        data.toLocaleDateString("pt-BR") +
        "<br>" +
        data.toLocaleTimeString("pt-BR", {
            hour: "2-digit",
            minute: "2-digit"
        })
    );
}

async function carregarHistorico() {
    try {
        const response = await fetch("/cobrancas/historico");
        const data = await response.json();

        historico.innerHTML = "";

        data.forEach(item => {
            historico.innerHTML += `
                <tr>
                    <td>${formatarData(item.data_envio)}</td>
                    <td>${item.cliente_nome}</td>
                    <td>${item.email_cliente}</td>
                    <td>${item.quantidade_boletos}</td>
                    <td>R$ ${formatarMoeda(item.valor_total)}</td>
                    <td>
                        <span class="status ${item.status}">
                            ${item.status}
                        </span>
                    </td>
                    <td>
                        <select onchange="atualizarStatus(${item.id}, this.value)">
                            <option value="">Selecionar</option>
                            <option value="pendente">Pendente</option>
                            <option value="cliente_respondeu">Cliente respondeu</option>
                            <option value="pago">Pago</option>
                            <option value="sem_resposta">Sem resposta</option>
                            <option value="encaminhar_extrajudicial">Encaminhar extrajudicial</option>
                        </select>
                    </td>
                    <td>
                        <button onclick="excluirCobranca(${item.id})">
                            Excluir
                        </button>
                    </td>
                </tr>
            `;
        });

    } catch (error) {
        console.error(error);
    }
}

async function atualizarStatus(id, status) {
    if (!status) return;

    await fetch(`/cobrancas/${id}/status`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            status: status
        })
    });

    carregarHistorico();
}

async function excluirCobranca(id) {
    const confirmar = confirm("Deseja realmente excluir esta cobrança?");

    if (!confirmar) return;

    await fetch(`/cobrancas/${id}`, {
        method: "DELETE"
    });

    carregarHistorico();
}

carregarHistorico();