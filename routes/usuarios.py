from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

import db as db_module
from helpers import registrar_log
from seguranca import admin_required


def register(app):
    @app.route("/usuarios")
    @admin_required
    def listar_usuarios():
        db = db_module.get_db()
        usuarios = db.execute("SELECT * FROM usuario ORDER BY nome").fetchall()
        return render_template("usuarios_list.html", usuarios=usuarios)

    @app.route("/usuarios/novo", methods=["GET", "POST"])
    @admin_required
    def novo_usuario():
        if request.method == "POST":
            nome = request.form["nome"].strip()
            login_novo = request.form["login"].strip()
            senha = request.form["senha"]
            tipo_usuario = request.form["tipo_usuario"]
            oab = request.form.get("oab", "").strip()

            erro = None
            if not nome or not login_novo or not senha:
                erro = "Preencha todos os campos obrigatórios."
            elif tipo_usuario not in ("administrador", "advogado"):
                erro = "Tipo de usuário inválido."

            db = db_module.get_db()
            if erro is None:
                existente = db.execute(
                    "SELECT id FROM usuario WHERE login = ?", (login_novo,)
                ).fetchone()
                if existente:
                    erro = f"Já existe um usuário com o login '{login_novo}'."

            if erro:
                flash(erro, "erro")
            else:
                cur = db.execute(
                    """
                    INSERT INTO usuario (nome, login, senha_hash, tipo_usuario, oab, ativo)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (nome, login_novo, generate_password_hash(senha), tipo_usuario, oab or None),
                )
                registrar_log(
                    db, "criar", "usuario", cur.lastrowid,
                    f"Usuário '{login_novo}' ({tipo_usuario}) cadastrado.",
                )
                db.commit()
                flash("Usuário cadastrado com sucesso.", "sucesso")
                return redirect(url_for("listar_usuarios"))

        return render_template("usuario_form.html", usuario=None)

    @app.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
    @admin_required
    def editar_usuario(usuario_id):
        db = db_module.get_db()
        usuario = db.execute("SELECT * FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
        if usuario is None:
            flash("Usuário não encontrado.", "erro")
            return redirect(url_for("listar_usuarios"))

        if request.method == "POST":
            nome = request.form["nome"].strip()
            login_novo = request.form["login"].strip()
            tipo_usuario = request.form["tipo_usuario"]
            oab = request.form.get("oab", "").strip()

            erro = None
            if not nome or not login_novo:
                erro = "Preencha todos os campos obrigatórios."
            elif tipo_usuario not in ("administrador", "advogado"):
                erro = "Tipo de usuário inválido."
            elif usuario_id == g.usuario["id"] and tipo_usuario != "administrador":
                erro = "Você não pode remover o próprio perfil de administrador."

            if erro is None:
                existente = db.execute(
                    "SELECT id FROM usuario WHERE login = ? AND id != ?", (login_novo, usuario_id)
                ).fetchone()
                if existente:
                    erro = f"Já existe um usuário com o login '{login_novo}'."

            if erro:
                flash(erro, "erro")
            else:
                db.execute(
                    "UPDATE usuario SET nome = ?, login = ?, tipo_usuario = ?, oab = ? WHERE id = ?",
                    (nome, login_novo, tipo_usuario, oab or None, usuario_id),
                )
                registrar_log(
                    db, "editar", "usuario", usuario_id, f"Usuário '{login_novo}' atualizado.",
                )
                db.commit()
                flash("Usuário atualizado com sucesso.", "sucesso")
                return redirect(url_for("listar_usuarios"))

        return render_template("usuario_form.html", usuario=usuario)

    @app.route("/usuarios/<int:usuario_id>/alternar-status", methods=["POST"])
    @admin_required
    def alternar_status_usuario(usuario_id):
        db = db_module.get_db()
        if usuario_id == g.usuario["id"]:
            flash("Você não pode desativar o próprio usuário.", "erro")
        else:
            alvo = db.execute("SELECT nome, ativo FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
            db.execute("UPDATE usuario SET ativo = NOT ativo WHERE id = ?", (usuario_id,))
            if alvo is not None:
                acao_texto = "desativado" if alvo["ativo"] else "ativado"
                registrar_log(
                    db, "editar", "usuario", usuario_id,
                    f"Usuário '{alvo['nome']}' {acao_texto}.",
                )
            db.commit()
            flash("Status do usuário atualizado.", "sucesso")
        return redirect(url_for("listar_usuarios"))

    @app.route("/usuarios/<int:usuario_id>/redefinir-senha", methods=["POST"])
    @admin_required
    def redefinir_senha_usuario(usuario_id):
        db = db_module.get_db()
        alvo = db.execute("SELECT nome FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
        if alvo is None:
            flash("Usuário não encontrado.", "erro")
            return redirect(url_for("listar_usuarios"))

        nova_senha = request.form.get("nova_senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")
        if len(nova_senha) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "erro")
        elif nova_senha != confirmar_senha:
            flash("A confirmação de senha não confere.", "erro")
        else:
            db.execute(
                """
                UPDATE usuario SET senha_hash = ?, tentativas_falhas = 0, bloqueado_ate = NULL
                WHERE id = ?
                """,
                (generate_password_hash(nova_senha), usuario_id),
            )
            registrar_log(
                db, "editar", "usuario", usuario_id,
                f"Senha de '{alvo['nome']}' redefinida pelo administrador.",
            )
            db.commit()
            flash(f"Senha de {alvo['nome']} redefinida com sucesso.", "sucesso")
        return redirect(url_for("listar_usuarios"))
