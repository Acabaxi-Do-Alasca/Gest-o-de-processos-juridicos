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
});

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
