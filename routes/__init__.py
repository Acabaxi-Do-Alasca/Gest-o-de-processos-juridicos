from . import (
    auditoria, auth, configuracoes, dashboard, documentos, movimentacoes, perfil, prazos,
    privacidade, processos, usuarios,
)


def register_routes(app):
    auth.register(app)
    dashboard.register(app)
    processos.register(app)
    prazos.register(app)
    movimentacoes.register(app)
    documentos.register(app)
    perfil.register(app)
    usuarios.register(app)
    configuracoes.register(app)
    auditoria.register(app)
    privacidade.register(app)
