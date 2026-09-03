from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db as db_module
from helpers import registrar_log
from seguranca import login_required


def register(app):
    @app.route("/perfil")
    @login_required
    def perfil():
        return render_template("perfil.html")

    @app.route("/perfil/senha", methods=["POST"])
    @login_required
    def alterar_senha():
        db = db_module.get_db()
        senha_atual = request.form["senha_atual"]
        nova_senha = request.form["nova_senha"]
        confirmar_senha = request.form["confirmar_senha"]

        erro = None
        if not check_password_hash(g.usuario["senha_hash"], senha_atual):
            erro = "Senha atual incorreta."
        elif len(nova_senha) < 6:
            erro = "A nova senha deve ter pelo menos 6 caracteres."
        elif nova_senha != confirmar_senha:
            erro = "A confirmação de senha não confere."

        if erro:
            flash(erro, "erro")
        else:
            db.execute(
                "UPDATE usuario SET senha_hash = ? WHERE id = ?",
                (generate_password_hash(nova_senha), g.usuario["id"]),
            )
            registrar_log(db, "editar", "usuario", g.usuario["id"], "Senha alterada pelo próprio usuário.")
            db.commit()
            flash("Senha atualizada com sucesso.", "sucesso")
        return redirect(url_for("perfil"))
