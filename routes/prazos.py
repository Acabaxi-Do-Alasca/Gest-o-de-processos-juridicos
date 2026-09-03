from datetime import date

from flask import flash, g, redirect, render_template, request, url_for

import db as db_module
from helpers import (
    buscar_advogados, buscar_processo_ou_404, buscar_processos_resumo, parse_data,
    registrar_log, rotulo_relativo,
)
from seguranca import eh_admin, login_required, verificar_acesso_processo


def _buscar_prazo_ou_404(db, prazo_id):
    prazo = db.execute("SELECT * FROM prazo WHERE id = ?", (prazo_id,)).fetchone()
    if prazo is None:
        flash("Prazo não encontrado.", "erro")
    return prazo


PAGINA_TAMANHO = 50


def register(app):
    @app.route("/prazos")
    @login_required
    def listar_prazos():
        db = db_module.get_db()
        restringir = not eh_admin()
        pagina = max(1, request.args.get("pagina", 1, type=int))
        filtro_sql = " AND processo.id_advogado_responsavel = ?" if restringir else ""
        parametros_base = [g.usuario["id"]] if restringir else []

        # Contagens (Vencidos/Próximos/No prazo) sobre TODOS os prazos em aberto, sem
        # paginar — são só datas, baratas de ler mesmo em volume; evita que os cards do
        # topo mintam sobre o total só porque a lista abaixo está paginada.
        datas = db.execute(
            f"""
            SELECT prazo.data_prazo FROM prazo
            JOIN processo ON processo.id = prazo.id_processo
            WHERE prazo.cumprido = 0{filtro_sql}
            """,
            parametros_base,
        ).fetchall()
        contagem = {"no_prazo": 0, "proximos": 0, "vencidos": 0}
        for d in datas:
            dias = (parse_data(d["data_prazo"]) - date.today()).days
            if dias < 0:
                contagem["vencidos"] += 1
            elif dias <= 7:
                contagem["proximos"] += 1
            else:
                contagem["no_prazo"] += 1

        rows = db.execute(
            f"""
            SELECT prazo.*, processo.numero_processo, processo.assunto, usuario.nome AS responsavel_nome
            FROM prazo
            JOIN processo ON processo.id = prazo.id_processo
            JOIN usuario ON usuario.id = prazo.id_responsavel
            WHERE prazo.cumprido = 0{filtro_sql}
            ORDER BY prazo.data_prazo ASC
            LIMIT ? OFFSET ?
            """,
            parametros_base + [PAGINA_TAMANHO + 1, (pagina - 1) * PAGINA_TAMANHO],
        ).fetchall()
        tem_proxima = len(rows) > PAGINA_TAMANHO
        rows = rows[:PAGINA_TAMANHO]

        buckets = {"atrasados": [], "hoje": [], "amanha": [], "semana": [], "depois": []}
        for p in rows:
            dias = (parse_data(p["data_prazo"]) - date.today()).days
            item = {"prazo": p, "rotulo": rotulo_relativo(p["data_prazo"])}
            if dias < 0:
                buckets["atrasados"].append(item)
            elif dias == 0:
                buckets["hoje"].append(item)
            elif dias == 1:
                buckets["amanha"].append(item)
            elif dias <= 7:
                buckets["semana"].append(item)
            else:
                buckets["depois"].append(item)

        secoes = [
            ("Atrasados", buckets["atrasados"], "status-vencido"),
            ("Hoje", buckets["hoje"], "status-vencido"),
            ("Amanhã", buckets["amanha"], "status-proximo"),
            ("Esta semana", buckets["semana"], "status-proximo"),
            ("Mais adiante", buckets["depois"], "status-no-prazo"),
        ]
        secoes = [s for s in secoes if s[1]]

        return render_template(
            "prazos_list.html", secoes=secoes, contagem=contagem, pagina=pagina, tem_proxima=tem_proxima
        )

    @app.route("/prazos/novo", methods=["GET", "POST"])
    @login_required
    def novo_prazo():
        db = db_module.get_db()
        processo_id = request.args.get("processo_id", type=int) or request.form.get("id_processo", type=int)
        processo = buscar_processo_ou_404(db, processo_id) if processo_id else None
        if processo is not None:
            verificar_acesso_processo(processo)
        advogados = buscar_advogados(db)
        processos = buscar_processos_resumo(db) if processo is None else None

        if request.method == "POST":
            id_processo = request.form.get("id_processo", type=int)
            descricao = request.form["descricao"].strip()
            data_prazo = request.form["data_prazo"]
            id_responsavel = request.form["id_responsavel"] if eh_admin() else str(g.usuario["id"])
            erro = None
            if not id_processo or not descricao or not data_prazo or not id_responsavel:
                erro = "Preencha todos os campos do prazo."
            else:
                processo_alvo = buscar_processo_ou_404(db, id_processo)
                if processo_alvo is None:
                    erro = "Processo não encontrado."
                else:
                    verificar_acesso_processo(processo_alvo)
                    try:
                        parse_data(data_prazo)
                    except ValueError:
                        erro = "Data do prazo inválida."
            if erro:
                flash(erro, "erro")
            else:
                cur = db.execute(
                    "INSERT INTO prazo (id_processo, descricao, data_prazo, id_responsavel, cumprido) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (id_processo, descricao, data_prazo, id_responsavel),
                )
                registrar_log(
                    db, "criar", "prazo", cur.lastrowid,
                    f"Prazo '{descricao}' cadastrado para o processo {processo_alvo['numero_processo']}.",
                )
                db.commit()
                flash("Prazo cadastrado com sucesso.", "sucesso")
                return redirect(url_for("detalhe_processo", processo_id=id_processo, aba="prazos"))

        return render_template(
            "prazo_form.html", processo=processo, processos=processos, advogados=advogados, prazo=None
        )

    @app.route("/prazos/<int:prazo_id>/cumprir", methods=["POST"])
    @login_required
    def cumprir_prazo(prazo_id):
        db = db_module.get_db()
        prazo = _buscar_prazo_ou_404(db, prazo_id)
        if prazo is None:
            return redirect(url_for("listar_prazos"))
        processo = buscar_processo_ou_404(db, prazo["id_processo"])
        if processo is not None:
            verificar_acesso_processo(processo)
        db.execute("UPDATE prazo SET cumprido = 1 WHERE id = ?", (prazo_id,))
        registrar_log(
            db, "editar", "prazo", prazo_id,
            f"Prazo '{prazo['descricao']}' marcado como cumprido.",
        )
        db.commit()
        flash("Prazo marcado como cumprido.", "sucesso")
        destino = request.form.get("origem")
        if destino == "prazos":
            return redirect(url_for("listar_prazos"))
        return redirect(url_for("detalhe_processo", processo_id=prazo["id_processo"], aba="prazos"))

    @app.route("/prazos/<int:prazo_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_prazo(prazo_id):
        db = db_module.get_db()
        prazo = _buscar_prazo_ou_404(db, prazo_id)
        if prazo is None:
            return redirect(url_for("listar_prazos"))
        processo = buscar_processo_ou_404(db, prazo["id_processo"])
        if processo is None:
            return redirect(url_for("listar_prazos"))
        verificar_acesso_processo(processo)
        advogados = buscar_advogados(db, incluir_inativo_id=prazo["id_responsavel"])

        if request.method == "POST":
            descricao = request.form["descricao"].strip()
            data_prazo = request.form["data_prazo"]
            id_responsavel = request.form["id_responsavel"] if eh_admin() else str(g.usuario["id"])
            erro = None
            if not descricao or not data_prazo or not id_responsavel:
                erro = "Preencha todos os campos do prazo."
            else:
                try:
                    parse_data(data_prazo)
                except ValueError:
                    erro = "Data do prazo inválida."
            if erro:
                flash(erro, "erro")
            else:
                db.execute(
                    "UPDATE prazo SET descricao = ?, data_prazo = ?, id_responsavel = ? WHERE id = ?",
                    (descricao, data_prazo, id_responsavel, prazo_id),
                )
                registrar_log(db, "editar", "prazo", prazo_id, f"Prazo '{descricao}' atualizado.")
                db.commit()
                flash("Prazo atualizado com sucesso.", "sucesso")
                return redirect(url_for("detalhe_processo", processo_id=prazo["id_processo"], aba="prazos"))

        return render_template(
            "prazo_form.html", processo=processo, processos=None, advogados=advogados, prazo=prazo
        )

    @app.route("/prazos/<int:prazo_id>/excluir", methods=["POST"])
    @login_required
    def excluir_prazo(prazo_id):
        db = db_module.get_db()
        prazo = _buscar_prazo_ou_404(db, prazo_id)
        if prazo is None:
            return redirect(url_for("listar_prazos"))
        processo = buscar_processo_ou_404(db, prazo["id_processo"])
        if processo is not None:
            verificar_acesso_processo(processo)
        db.execute("DELETE FROM prazo WHERE id = ?", (prazo_id,))
        registrar_log(db, "excluir", "prazo", prazo_id, f"Prazo '{prazo['descricao']}' excluído.")
        db.commit()
        flash("Prazo excluído com sucesso.", "sucesso")
        destino = request.form.get("origem")
        if destino == "prazos":
            return redirect(url_for("listar_prazos"))
        return redirect(url_for("detalhe_processo", processo_id=prazo["id_processo"], aba="prazos"))
