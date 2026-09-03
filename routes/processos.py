import os
from datetime import date

from flask import current_app, flash, g, redirect, render_template, request, url_for

import db as db_module
from helpers import (
    MESES_PT, SITUACOES_PROCESSO, buscar_advogados, buscar_processo_ou_404, parse_data,
    registrar_log, status_prazo,
)
from seguranca import eh_admin, login_required, verificar_acesso_processo

PAGINA_TAMANHO = 30


def register(app):
    @app.route("/processos")
    @login_required
    def listar_processos():
        db = db_module.get_db()
        q = request.args.get("q", "").strip()
        advogado_id = request.args.get("advogado_id", "").strip()
        situacao = request.args.get("situacao", "").strip()
        pagina = max(1, request.args.get("pagina", 1, type=int))

        condicoes = []
        parametros = []
        if not eh_admin():
            condicoes.append("processo.id_advogado_responsavel = ?")
            parametros.append(g.usuario["id"])
        if q:
            condicoes.append(
                "(processo.numero_processo LIKE ? OR processo.parte_principal LIKE ? OR usuario.nome LIKE ?)"
            )
            parametros += [f"%{q}%", f"%{q}%", f"%{q}%"]
        if advogado_id and eh_admin():
            condicoes.append("processo.id_advogado_responsavel = ?")
            parametros.append(advogado_id)
        if situacao == "Aguardando":
            condicoes.append("processo.situacao IN ('Aguardando providência', 'Aguardando decisão')")
        elif situacao:
            condicoes.append("processo.situacao = ?")
            parametros.append(situacao)

        sql = """
            SELECT processo.*, usuario.nome AS advogado_nome,
                (SELECT MAX(data) FROM movimentacao WHERE movimentacao.id_processo = processo.id) AS ultima_movimentacao,
                (SELECT MIN(data_prazo) FROM prazo WHERE prazo.id_processo = processo.id AND prazo.cumprido = 0) AS proximo_prazo
            FROM processo
            JOIN usuario ON usuario.id = processo.id_advogado_responsavel
        """
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        sql += " ORDER BY processo.data_entrada DESC LIMIT ? OFFSET ?"
        parametros += [PAGINA_TAMANHO + 1, (pagina - 1) * PAGINA_TAMANHO]

        processos = db.execute(sql, parametros).fetchall()
        tem_proxima = len(processos) > PAGINA_TAMANHO
        processos = processos[:PAGINA_TAMANHO]
        if eh_admin():
            total = db.execute("SELECT COUNT(*) AS n FROM processo").fetchone()["n"]
        else:
            total = db.execute(
                "SELECT COUNT(*) AS n FROM processo WHERE id_advogado_responsavel = ?", (g.usuario["id"],)
            ).fetchone()["n"]
        advogados = buscar_advogados(db)
        return render_template(
            "processos_list.html",
            processos=processos,
            advogados=advogados,
            total=total,
            filtros={"q": q, "advogado_id": advogado_id, "situacao": situacao},
            pagina=pagina, tem_proxima=tem_proxima,
        )

    @app.route("/processos/novo", methods=["GET", "POST"])
    @login_required
    def novo_processo():
        db = db_module.get_db()
        advogados = buscar_advogados(db)

        if request.method == "POST":
            campos = _ler_campos_processo(request.form)
            if not eh_admin():
                campos["id_advogado_responsavel"] = str(g.usuario["id"])
            erro = _validar_campos_processo(campos)
            if erro is None:
                erro = _numero_processo_duplicado(db, campos["numero_processo"])
            if erro:
                flash(erro, "erro")
            else:
                cur = db.execute(
                    """
                    INSERT INTO processo
                        (numero_processo, tipo, assunto, parte_principal, comarca_orgao,
                         data_entrada, id_advogado_responsavel, situacao, observacoes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        campos["numero_processo"], campos["tipo"], campos["assunto"],
                        campos["parte_principal"], campos["comarca_orgao"], campos["data_entrada"],
                        campos["id_advogado_responsavel"], campos["situacao"], campos["observacoes"],
                    ),
                )
                registrar_log(
                    db, "criar", "processo", cur.lastrowid,
                    f"Processo {campos['numero_processo']} cadastrado.",
                )
                db.commit()
                flash("Processo cadastrado com sucesso.", "sucesso")
                return redirect(url_for("listar_processos"))

        return render_template("processo_form.html", processo=None, advogados=advogados)

    @app.route("/processos/<int:processo_id>")
    @login_required
    def detalhe_processo(processo_id):
        db = db_module.get_db()
        processo = buscar_processo_ou_404(db, processo_id)
        if processo is None:
            return redirect(url_for("listar_processos"))
        verificar_acesso_processo(processo)

        aba = request.args.get("aba", "geral")

        proximo_prazo_row = db.execute(
            """
            SELECT prazo.*, usuario.nome AS responsavel_nome
            FROM prazo JOIN usuario ON usuario.id = prazo.id_responsavel
            WHERE prazo.id_processo = ? AND prazo.cumprido = 0
            ORDER BY prazo.data_prazo ASC LIMIT 1
            """,
            (processo_id,),
        ).fetchone()
        proximo_prazo = None
        if proximo_prazo_row:
            d = parse_data(proximo_prazo_row["data_prazo"])
            dias = (d - date.today()).days
            if dias < 0:
                situacao_texto = f"Vencido há {abs(dias)} dia(s)"
            elif dias == 0:
                situacao_texto = "Vence hoje"
            elif dias == 1:
                situacao_texto = "Vence amanhã"
            else:
                situacao_texto = f"Faltam {dias} dias"
            proximo_prazo = {
                "dia": f"{d.day:02d}", "mes": MESES_PT[d.month - 1].upper(),
                "descricao": proximo_prazo_row["descricao"], "situacao_texto": situacao_texto,
            }

        ultima_movimentacao_row = db.execute(
            """
            SELECT movimentacao.*, usuario.nome AS usuario_nome
            FROM movimentacao JOIN usuario ON usuario.id = movimentacao.id_usuario_registro
            WHERE movimentacao.id_processo = ?
            ORDER BY movimentacao.data DESC, movimentacao.id DESC LIMIT 1
            """,
            (processo_id,),
        ).fetchone()

        prazos = db.execute(
            """
            SELECT prazo.*, usuario.nome AS responsavel_nome
            FROM prazo JOIN usuario ON usuario.id = prazo.id_responsavel
            WHERE prazo.id_processo = ? ORDER BY prazo.data_prazo
            """,
            (processo_id,),
        ).fetchall()
        prazos_com_status = [
            {"prazo": p, "rotulo": status_prazo(p["data_prazo"], p["cumprido"])[0],
             "classe": status_prazo(p["data_prazo"], p["cumprido"])[1]}
            for p in prazos
        ]

        movimentacoes = db.execute(
            """
            SELECT movimentacao.*, usuario.nome AS usuario_nome
            FROM movimentacao JOIN usuario ON usuario.id = movimentacao.id_usuario_registro
            WHERE movimentacao.id_processo = ?
            ORDER BY movimentacao.data DESC, movimentacao.id DESC
            """,
            (processo_id,),
        ).fetchall()

        documentos = db.execute(
            """
            SELECT documento.*, usuario.nome AS usuario_nome
            FROM documento JOIN usuario ON usuario.id = documento.id_usuario_upload
            WHERE documento.id_processo = ? ORDER BY documento.data_upload DESC
            """,
            (processo_id,),
        ).fetchall()

        return render_template(
            "processo_detail.html",
            processo=processo, aba=aba,
            proximo_prazo=proximo_prazo, ultima_movimentacao=ultima_movimentacao_row,
            prazos=prazos_com_status, movimentacoes=movimentacoes, documentos=documentos,
        )

    @app.route("/processos/<int:processo_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_processo(processo_id):
        db = db_module.get_db()
        processo = buscar_processo_ou_404(db, processo_id)
        if processo is None:
            return redirect(url_for("listar_processos"))
        verificar_acesso_processo(processo)
        advogados = buscar_advogados(db, incluir_inativo_id=processo["id_advogado_responsavel"])

        if request.method == "POST":
            campos = _ler_campos_processo(request.form)
            if not eh_admin():
                campos["id_advogado_responsavel"] = str(g.usuario["id"])
            erro = _validar_campos_processo(campos)
            if erro is None:
                erro = _numero_processo_duplicado(db, campos["numero_processo"], excluir_id=processo_id)
            if erro:
                flash(erro, "erro")
            else:
                db.execute(
                    """
                    UPDATE processo SET
                        numero_processo = ?, tipo = ?, assunto = ?, parte_principal = ?,
                        comarca_orgao = ?, data_entrada = ?, id_advogado_responsavel = ?,
                        situacao = ?, observacoes = ?
                    WHERE id = ?
                    """,
                    (
                        campos["numero_processo"], campos["tipo"], campos["assunto"],
                        campos["parte_principal"], campos["comarca_orgao"], campos["data_entrada"],
                        campos["id_advogado_responsavel"], campos["situacao"], campos["observacoes"],
                        processo_id,
                    ),
                )
                registrar_log(
                    db, "editar", "processo", processo_id,
                    f"Processo {campos['numero_processo']} atualizado.",
                )
                db.commit()
                flash("Processo atualizado com sucesso.", "sucesso")
                return redirect(url_for("detalhe_processo", processo_id=processo_id))

        return render_template("processo_form.html", processo=processo, advogados=advogados)

    @app.route("/processos/<int:processo_id>/excluir", methods=["POST"])
    @login_required
    def excluir_processo(processo_id):
        db = db_module.get_db()
        processo = buscar_processo_ou_404(db, processo_id)
        if processo is None:
            return redirect(url_for("listar_processos"))
        verificar_acesso_processo(processo)
        arquivos = db.execute(
            "SELECT nome_arquivo FROM documento WHERE id_processo = ? AND nome_arquivo IS NOT NULL",
            (processo_id,),
        ).fetchall()
        for arquivo in arquivos:
            caminho = os.path.join(current_app.config["UPLOAD_FOLDER"], arquivo["nome_arquivo"])
            if os.path.exists(caminho):
                os.remove(caminho)
        db.execute("DELETE FROM prazo WHERE id_processo = ?", (processo_id,))
        db.execute("DELETE FROM movimentacao WHERE id_processo = ?", (processo_id,))
        db.execute("DELETE FROM documento WHERE id_processo = ?", (processo_id,))
        db.execute("DELETE FROM processo WHERE id = ?", (processo_id,))
        registrar_log(
            db, "excluir", "processo", processo_id,
            f"Processo {processo['numero_processo']} excluído (com prazos, movimentações e documentos vinculados).",
        )
        db.commit()
        flash("Processo excluído com sucesso.", "sucesso")
        return redirect(url_for("listar_processos"))


def _ler_campos_processo(form):
    return {
        "numero_processo": form["numero_processo"].strip(),
        "tipo": form["tipo"].strip(),
        "assunto": form["assunto"].strip(),
        "parte_principal": form["parte_principal"].strip(),
        "comarca_orgao": form["comarca_orgao"].strip(),
        "data_entrada": form["data_entrada"],
        "id_advogado_responsavel": form["id_advogado_responsavel"],
        "situacao": form["situacao"],
        "observacoes": form.get("observacoes", "").strip(),
    }


def _numero_processo_duplicado(db, numero_processo, excluir_id=None):
    sql = "SELECT id FROM processo WHERE numero_processo = ?"
    parametros = [numero_processo]
    if excluir_id is not None:
        sql += " AND id != ?"
        parametros.append(excluir_id)
    if db.execute(sql, parametros).fetchone():
        return f"Já existe um processo cadastrado com o número '{numero_processo}'."
    return None


def _validar_campos_processo(campos):
    obrigatorios = ["numero_processo", "tipo", "assunto", "parte_principal", "comarca_orgao",
                     "data_entrada", "id_advogado_responsavel", "situacao"]
    for campo in obrigatorios:
        if not campos[campo]:
            return "Preencha todos os campos obrigatórios do processo."
    if campos["situacao"] not in SITUACOES_PROCESSO:
        return "Situação de processo inválida."
    try:
        parse_data(campos["data_entrada"])
    except ValueError:
        return "Data de entrada inválida."
    return None
