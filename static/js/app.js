// Toasts: some tempo depois de aparecer.
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".toast").forEach((toast) => {
        setTimeout(() => {
            toast.classList.add("saindo");
            setTimeout(() => toast.remove(), 200);
        }, 4200);
    });

    // Fecha o menu do usuário e o painel de filtros ao clicar fora.
    document.addEventListener("click", (evento) => {
        document.querySelectorAll("details[open]").forEach((det) => {
            if (!det.contains(evento.target)) det.removeAttribute("open");
        });
    });

    // Evita registro duplicado por clique duplo: desabilita o botão de envio dos
    // formulários que alteram dados assim que o envio é disparado.
    document.addEventListener("submit", (evento) => {
        if (evento.target.method !== "post") return;
        const botao = evento.target.querySelector('button[type="submit"]');
        if (botao) botao.disabled = true;
    });

    const campoNumeroProcesso = document.getElementById("numero_processo");
    if (campoNumeroProcesso) {
        aplicarMascaraProcesso(campoNumeroProcesso);
        campoNumeroProcesso.addEventListener("input", () => aplicarMascaraProcesso(campoNumeroProcesso));
    }
});

// Máscara do número CNJ do processo: NNNNNNN-DD.AAAA.J.TR.OOOO (20 dígitos).
function aplicarMascaraProcesso(campo) {
    const digitos = campo.value.replace(/\D/g, "").slice(0, 20);
    const partes = [
        digitos.slice(0, 7),
        digitos.slice(7, 9),
        digitos.slice(9, 13),
        digitos.slice(13, 14),
        digitos.slice(14, 16),
        digitos.slice(16, 20),
    ];
    let formatado = partes[0];
    if (partes[1]) formatado += "-" + partes[1];
    if (partes[2]) formatado += "." + partes[2];
    if (partes[3]) formatado += "." + partes[3];
    if (partes[4]) formatado += "." + partes[4];
    if (partes[5]) formatado += "." + partes[5];
    campo.value = formatado;
}

// Reabilita botões de envio ao voltar para a página pelo histórico do navegador
// (bfcache), para não deixar um formulário preso "desabilitado para sempre".
window.addEventListener("pageshow", () => {
    document.querySelectorAll('button[type="submit"]:disabled').forEach((botao) => {
        botao.disabled = false;
    });
});

function abrirMenuMobile() {
    document.querySelector(".sidebar").classList.add("aberta");
    document.querySelector(".sidebar-backdrop").classList.add("aberta");
}

function fecharMenuMobile() {
    document.querySelector(".sidebar").classList.remove("aberta");
    document.querySelector(".sidebar-backdrop").classList.remove("aberta");
}

function abrirConfirmacao(id) {
    const dialogo = document.getElementById(id);
    if (dialogo) dialogo.showModal();
}

function fecharConfirmacao(id) {
    const dialogo = document.getElementById(id);
    if (dialogo) dialogo.close();
}
