from datetime import datetime, timedelta

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import db as db_module
from helpers import registrar_log

MAX_TENTATIVAS_LOGIN = 5
BLOQUEIO_MINUTOS = 15


def _next_seguro(destino):
    """Só aceita `next` como caminho relativo interno — nunca uma URL externa (proteção
    contra redirecionamento aberto/phishing: `?next=https://site-malicioso.com`)."""
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return None


def register(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.usuario is not None:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            login_informado = request.form["login"].strip()
            senha = request.form["senha"]
            db = db_module.get_db()
            usuario = db.execute(
                "SELECT * FROM usuario WHERE login = ?", (login_informado,)
            ).fetchone()

            agora = datetime.now()
            bloqueado_ate = (
                datetime.strptime(usuario["bloqueado_ate"], "%Y-%m-%dT%H:%M:%S")
                if usuario and usuario["bloqueado_ate"] else None
            )

            erro = None
            senha_incorreta = False
            if bloqueado_ate and agora < bloqueado_ate:
                erro = "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."
            elif usuario is None or not check_password_hash(usuario["senha_hash"], senha):
                erro = "Usuário ou senha inválidos."
                senha_incorreta = usuario is not None
            elif not usuario["ativo"]:
                erro = "Este usuário está desativado. Procure o administrador."

            if erro is None:
                anterior = usuario["ultimo_acesso"]
                session.clear()
                session["usuario_id"] = usuario["id"]
                session["ultimo_acesso_anterior"] = anterior
                db.execute(
                    """
                    UPDATE usuario SET ultimo_acesso = ?, tentativas_falhas = 0, bloqueado_ate = NULL
                    WHERE id = ?
                    """,
                    (agora.strftime("%Y-%m-%dT%H:%M:%S"), usuario["id"]),
                )
                registrar_log(db, "login", "usuario", usuario["id"], "Login realizado.", usuario=usuario)
                db.commit()
                destino = _next_seguro(request.args.get("next")) or url_for("dashboard")
                return redirect(destino)

            # Bloqueio por tentativas repetidas (proteção contra força bruta — Seção 6.3):
            # só conta a tentativa quando a senha realmente estava errada para uma conta
            # existente — não penaliza login inexistente nem uma conta já bloqueada/desativada.
            if senha_incorreta:
                tentativas = usuario["tentativas_falhas"] + 1
                novo_bloqueio = None
                if tentativas >= MAX_TENTATIVAS_LOGIN:
                    novo_bloqueio = (agora + timedelta(minutes=BLOQUEIO_MINUTOS)).strftime("%Y-%m-%dT%H:%M:%S")
                    tentativas = 0
                    erro = f"Muitas tentativas de login. Conta bloqueada por {BLOQUEIO_MINUTOS} minutos."
                db.execute(
                    "UPDATE usuario SET tentativas_falhas = ?, bloqueado_ate = ? WHERE id = ?",
                    (tentativas, novo_bloqueio, usuario["id"]),
                )

            registrar_log(
                db, "login_falho", "usuario", usuario["id"] if usuario else None,
                f"Tentativa de login mal sucedida para o login '{login_informado}'.",
                usuario=usuario,
            )
            db.commit()
            flash(erro, "erro")

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
