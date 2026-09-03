from datetime import datetime

from flask import flash, g, redirect, render_template, request, url_for

import db as db_module
from helpers import buscar_processo_ou_404, buscar_processos_resumo, parse_data, registrar_log
from seguranca import eh_admin, login_required, verificar_acesso_processo

PAGINA_TAMANHO = 30

SUGESTOES = ["Intimação recebida", "Petição protocolada", "Audiência realizada",
             "Despacho", "Decisão", "Sentença"]


def _buscar_movimentacao_ou_404(db, movimentacao_id):
    movimentacao = db.execute(
        "SELECT * FROM movimentacao WHERE id = ?", (movimentacao_id,)
    ).fetchone()
    if movimentacao is None:
        flash("Movimentação não encontrada.", "erro")
    return movimentacao


def register(app):
    @app.route("/movimentacoes")
    @login_required
    def listar_movimentacoes():
        db = db_module.get_db()
        q = request.args.get("q", "").strip()
        pagina = max(1, request.args.get("pagina", 1, type=int))
        condicoes = []
        parametros = []
        if not eh_admin():
            condicoes.append("processo.id_advogado_responsavel = ?")
            parametros.append(g.usuario["id"])
        if q:
            condicoes.append("(movimentacao.descricao LIKE ? OR processo.numero_processo LIKE ?)")
            parametros += [f"%{q}%", f"%{q}%"]
        sql = """
            SELECT movimentacao.*, processo.numero_processo, usuario.nome AS usuario_nome
            FROM movimentacao
            JOIN processo ON processo.id = movimentacao.id_processo
            JOIN usuario ON usuario.id = movimentacao.id_usuario_registro
        """
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        sql += " ORDER BY movimentacao.data DESC, movimentacao.id DESC LIMIT ? OFFSET ?"
        parametros += [PAGINA_TAMANHO + 1, (pagina - 1) * PAGINA_TAMANHO]
        movimentacoes = db.execute(sql, parametros).fetchall()
        tem_proxima = len(movimentacoes) > PAGINA_TAMANHO
        movimentacoes = movimentacoes[:PAGINA_TAMANHO]
        return render_template(
            "movimentacoes_list.html", movimentacoes=movimentacoes, q=q, pagina=pagina, tem_proxima=tem_proxima
        )

    @app.route("/movimentacoes/novo", methods=["GET", "POST"])
    @login_required
    def nova_movimentacao():
        db = db_module.get_db()
        processo_id = request.args.get("processo_id", type=int) or request.form.get("id_processo", type=int)
        processo = buscar_processo_ou_404(db, processo_id) if processo_id else None
        if processo is not None:
            verificar_acesso_processo(processo)
        processos = buscar_processos_resumo(db) if processo is None else None

        if request.method == "POST":
            id_processo = request.form.get("id_processo", type=int)
            descricao = request.form["descricao"].strip()
            data_mov = request.form["data"]
            erro = None
            if not id_processo or not descricao or not data_mov:
                erro = "Preencha todos os campos da movimentação."
            else:
                processo_alvo = buscar_processo_ou_404(db, id_processo)
                if processo_alvo is None:
                    erro = "Processo não encontrado."
                else:
                    verificar_acesso_processo(processo_alvo)
                    try:
                        parse_data(data_mov)
                    except ValueError:
                        erro = "Data da movimentação inválida."
            if erro:
                flash(erro, "erro")
            else:
                cur = db.execute(
                    """
                    INSERT INTO movimentacao (id_processo, data, descricao, id_usuario_registro, hora_registro)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (id_processo, data_mov, descricao, g.usuario["id"], datetime.now().strftime("%H:%M")),
                )
                registrar_log(
                    db, "criar", "movimentacao", cur.lastrowid,
                    f"Movimentação '{descricao}' registrada no processo {processo_alvo['numero_processo']}.",
                )
                db.commit()
                flash("Movimentação registrada com sucesso.", "sucesso")
                return redirect(url_for("detalhe_processo", processo_id=id_processo, aba="movimentacoes"))

        return render_template(
            "movimentacao_form.html", processo=processo, processos=processos,
            sugestoes=SUGESTOES, movimentacao=None,
        )

    @app.route("/movimentacoes/<int:movimentacao_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_movimentacao(movimentacao_id):
        db = db_module.get_db()
        movimentacao = _buscar_movimentacao_ou_404(db, movimentacao_id)
        if movimentacao is None:
            return redirect(url_for("listar_movimentacoes"))
        processo = buscar_processo_ou_404(db, movimentacao["id_processo"])
        if processo is None:
            return redirect(url_for("listar_movimentacoes"))
        verificar_acesso_processo(processo)

        if request.method == "POST":
            descricao = request.form["descricao"].strip()
            data_mov = request.form["data"]
            erro = None
            if not descricao or not data_mov:
                erro = "Preencha todos os campos da movimentação."
            else:
                try:
                    parse_data(data_mov)
                except ValueError:
                    erro = "Data da movimentação inválida."
            if erro:
                flash(erro, "erro")
            else:
                db.execute(
                    "UPDATE movimentacao SET descricao = ?, data = ? WHERE id = ?",
                    (descricao, data_mov, movimentacao_id),
                )
                registrar_log(
                    db, "editar", "movimentacao", movimentacao_id,
                    f"Movimentação '{descricao}' atualizada.",
                )
                db.commit()
                flash("Movimentação atualizada com sucesso.", "sucesso")
                return redirect(url_for(
                    "detalhe_processo", processo_id=movimentacao["id_processo"], aba="movimentacoes"
                ))

        return render_template(
            "movimentacao_form.html", processo=processo, processos=None,
            sugestoes=SUGESTOES, movimentacao=movimentacao,
        )

    @app.route("/movimentacoes/<int:movimentacao_id>/excluir", methods=["POST"])
    @login_required
    def excluir_movimentacao(movimentacao_id):
        db = db_module.get_db()
        movimentacao = _buscar_movimentacao_ou_404(db, movimentacao_id)
        if movimentacao is None:
            return redirect(url_for("listar_movimentacoes"))
        processo = buscar_processo_ou_404(db, movimentacao["id_processo"])
        if processo is not None:
            verificar_acesso_processo(processo)
        db.execute("DELETE FROM movimentacao WHERE id = ?", (movimentacao_id,))
        registrar_log(
            db, "excluir", "movimentacao", movimentacao_id,
            f"Movimentação '{movimentacao['descricao']}' excluída.",
        )
        db.commit()
        flash("Movimentação excluída com sucesso.", "sucesso")
        return redirect(url_for(
            "detalhe_processo", processo_id=movimentacao["id_processo"], aba="movimentacoes"
        ))
