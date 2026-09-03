import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, g, render_template, request, session

import db as db_module
from csrf import obter_csrf_token, validar_csrf_do_formulario
from helpers import (
    CONFIG_PADRAO,
    ENTIDADE_LABELS,
    SITUACOES_PROCESSO,
    buscar_configuracao,
    classe_acao,
    extensao_documento,
    formatar_data_extenso,
    formatar_datahora,
    formatar_tamanho,
    iniciais,
    rotulo_acao,
    rotulo_entidade,
    situacao_classe,
)
from routes import register_routes

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = INSTANCE_DIR / "documentos"


def _obter_secret_key():
    """Usa SECRET_KEY do ambiente se definida; senão gera uma chave aleatória na
    primeira execução e a reaproveita nas próximas (evita `SECRET_KEY="dev"` fixo
    no código-fonte, exigido pelas boas práticas de segurança da Seção 6.3)."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    arquivo_chave = INSTANCE_DIR / "secret_key.txt"
    if arquivo_chave.exists():
        return arquivo_chave.read_text(encoding="utf-8").strip()
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    chave = secrets.token_hex(32)
    arquivo_chave.write_text(chave, encoding="utf-8")
    return chave


def create_app():
    app = Flask(__name__)
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=_obter_secret_key(),
        DATABASE=str(INSTANCE_DIR / "sistema.sqlite"),
        UPLOAD_FOLDER=str(UPLOAD_DIR),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,  # 20 MB por arquivo
        SESSION_COOKIE_SAMESITE="Lax",  # reforça a proteção contra CSRF (Seção 6.3)
    )
    db_module.init_app(app)
    register_routes(app)
    register_hooks(app)
    app.jinja_env.filters["situacao_classe"] = situacao_classe
    app.jinja_env.filters["iniciais"] = iniciais
    app.jinja_env.filters["data_extenso"] = formatar_data_extenso
    app.jinja_env.filters["datahora"] = formatar_datahora
    app.jinja_env.filters["rotulo_acao"] = rotulo_acao
    app.jinja_env.filters["classe_acao"] = classe_acao
    app.jinja_env.filters["rotulo_entidade"] = rotulo_entidade
    app.jinja_env.filters["extensao"] = extensao_documento
    app.jinja_env.filters["tamanho"] = formatar_tamanho
    return app


def register_hooks(app):
    @app.after_request
    def aplicar_cabecalhos_seguranca(response):
        # Impede que o sistema seja embutido em <iframe> de terceiros (clickjacking) e
        # que o navegador tente "adivinhar" o tipo de um arquivo servido (Seção 6.3).
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Páginas autenticadas (dados de processos, documentos etc.) não devem ficar em
        # cache do navegador — relevante em computador compartilhado, mesmo após logout.
        if g.get("usuario") is not None and not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.before_request
    def carregar_usuario_logado():
        usuario_id = session.get("usuario_id")
        g.usuario = None
        if usuario_id is not None:
            try:
                db = db_module.get_db()
                g.usuario = db.execute(
                    "SELECT * FROM usuario WHERE id = ? AND ativo = 1", (usuario_id,)
                ).fetchone()
            except sqlite3.Error:
                # Banco indisponível: degrada para "não autenticado" em vez de quebrar
                # a requisição antes mesmo de chegar nas páginas de erro (400/403/404/500).
                g.usuario = None
            else:
                if g.usuario is None:
                    session.clear()

    @app.before_request
    def protecao_csrf():
        if request.method == "POST":
            validar_csrf_do_formulario()

    @app.context_processor
    def injetar_globais():
        anterior = session.get("ultimo_acesso_anterior")
        try:
            config = buscar_configuracao(db_module.get_db())
        except sqlite3.Error:
            config = dict(CONFIG_PADRAO)
        return {
            "usuario_logado": g.get("usuario"),
            "situacoes_processo": SITUACOES_PROCESSO,
            "config_geral": config,
            "ultimo_acesso_anterior": formatar_datahora(anterior) if anterior else None,
            "entidades_auditoria": ENTIDADE_LABELS,
            "csrf_token": obter_csrf_token(),
        }

    @app.errorhandler(403)
    def acesso_negado(e):
        return render_template("403.html"), 403

    @app.errorhandler(400)
    def requisicao_invalida(e):
        return render_template("400.html"), 400

    @app.errorhandler(413)
    def arquivo_muito_grande(e):
        return render_template("413.html"), 413

    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def erro_interno(e):
        return render_template("500.html"), 500


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
