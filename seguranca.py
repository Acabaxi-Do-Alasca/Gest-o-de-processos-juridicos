"""Autenticação e controle de acesso: decorators de rota e checagens de permissão."""
import functools

from flask import abort, g, redirect, request, url_for


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.usuario is None:
            destino = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=destino))
        return view(**kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.usuario is None:
            destino = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=destino))
        if g.usuario["tipo_usuario"] != "administrador":
            abort(403)
        return view(**kwargs)
    return wrapped


def eh_admin():
    return g.usuario["tipo_usuario"] == "administrador"


def verificar_acesso_processo(processo):
    """Um advogado só pode ver/alterar processos em que é o responsável; o administrador vê todos."""
    if not eh_admin() and processo["id_advogado_responsavel"] != g.usuario["id"]:
        abort(403)
