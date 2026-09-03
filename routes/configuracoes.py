from flask import flash, redirect, render_template, request, url_for

import db as db_module
from helpers import buscar_configuracao, registrar_log
from seguranca import admin_required


def register(app):
    @app.route("/configuracoes", methods=["GET", "POST"])
    @admin_required
    def configuracoes():
        db = db_module.get_db()
        if request.method == "POST":
            nome_instituicao = request.form["nome_instituicao"].strip()
            nome_sistema = request.form["nome_sistema"].strip()
            encarregado_nome = request.form["encarregado_nome"].strip()
            encarregado_contato = request.form["encarregado_contato"].strip()
            valores = (
                ("nome_instituicao", nome_instituicao),
                ("nome_sistema", nome_sistema),
                ("encarregado_nome", encarregado_nome),
                ("encarregado_contato", encarregado_contato),
            )
            for chave, valor in valores:
                db.execute(
                    "INSERT INTO configuracao (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                    (chave, valor),
                )
            registrar_log(db, "editar", "configuracao", None, "Configurações do sistema atualizadas.")
            db.commit()
            flash("Configurações atualizadas com sucesso.", "sucesso")
            return redirect(url_for("configuracoes"))

        return render_template("configuracoes.html", config=buscar_configuracao(db))
