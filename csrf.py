"""Proteção CSRF (Cross-Site Request Forgery) por token de sessão.

O projeto usa apenas Flask (sem Flask-WTF), então a proteção é implementada de
forma direta: cada sessão recebe um token aleatório; todo formulário POST deve
devolver esse token em um campo oculto `csrf_token`; toda requisição POST é
validada contra o token da sessão antes de chegar à rota (Seção 6.3 do
enunciado — "boas práticas complementares" de segurança).
"""
import hmac
import secrets

from flask import abort, request, session


def obter_csrf_token():
    """Garante que a sessão atual tenha um token e o retorna (para uso em templates)."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validar_csrf_do_formulario():
    """Aborta com 400 se o token enviado no POST não bater com o da sessão."""
    token_sessao = session.get("csrf_token")
    token_form = request.form.get("csrf_token")
    if not token_sessao or not token_form or not hmac.compare_digest(token_sessao, token_form):
        abort(400)
