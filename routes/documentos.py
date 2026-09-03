import os
import uuid
from datetime import date

from flask import (
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

import db as db_module
from helpers import buscar_processo_ou_404, buscar_processos_resumo, registrar_log
from seguranca import eh_admin, login_required, verificar_acesso_processo

EXTENSOES_PERMITIDAS = {"pdf", "doc", "docx"}
PAGINA_TAMANHO = 30


def _extensao(nome_arquivo):
    return nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""


def _arquivo_vazio(arquivo):
    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)
    return tamanho == 0


def _buscar_documento_ou_404(db, documento_id):
    documento = db.execute(
        """
        SELECT documento.*, processo.numero_processo, processo.id_advogado_responsavel
        FROM documento
        JOIN processo ON processo.id = documento.id_processo
        WHERE documento.id = ?
        """,
        (documento_id,),
    ).fetchone()
    if documento is None:
        flash("Documento não encontrado.", "erro")
    return documento


def _remover_arquivo(nome_arquivo):
    if not nome_arquivo:
        return
    caminho = os.path.join(current_app.config["UPLOAD_FOLDER"], nome_arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)


def _salvar_arquivo(arquivo, nome_original):
    """Salva o arquivo enviado com um nome único em disco; retorna (nome_arquivo, tamanho_bytes)."""
    nome_arquivo = f"{uuid.uuid4().hex}.{_extensao(nome_original)}"
    caminho = os.path.join(current_app.config["UPLOAD_FOLDER"], nome_arquivo)
    arquivo.save(caminho)
    return nome_arquivo, os.path.getsize(caminho)


def register(app):
    @app.route("/documentos")
    @login_required
    def listar_documentos():
        db = db_module.get_db()
        q = request.args.get("q", "").strip()
        pagina = max(1, request.args.get("pagina", 1, type=int))
        condicoes = []
        parametros = []
        if not eh_admin():
            condicoes.append("processo.id_advogado_responsavel = ?")
            parametros.append(g.usuario["id"])
        if q:
            condicoes.append("(documento.nome_documento LIKE ? OR processo.numero_processo LIKE ?)")
            parametros += [f"%{q}%", f"%{q}%"]
        sql = """
            SELECT documento.*, processo.numero_processo, usuario.nome AS usuario_nome
            FROM documento
            JOIN processo ON processo.id = documento.id_processo
            JOIN usuario ON usuario.id = documento.id_usuario_upload
        """
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        sql += " ORDER BY documento.data_upload DESC, documento.id DESC LIMIT ? OFFSET ?"
        parametros += [PAGINA_TAMANHO + 1, (pagina - 1) * PAGINA_TAMANHO]
        documentos = db.execute(sql, parametros).fetchall()
        tem_proxima = len(documentos) > PAGINA_TAMANHO
        documentos = documentos[:PAGINA_TAMANHO]
        return render_template(
            "documentos_list.html", documentos=documentos, q=q, pagina=pagina, tem_proxima=tem_proxima
        )

    @app.route("/documentos/novo", methods=["GET", "POST"])
    @login_required
    def novo_documento():
        db = db_module.get_db()
        processo_id = request.args.get("processo_id", type=int) or request.form.get("id_processo", type=int)
        processo = buscar_processo_ou_404(db, processo_id) if processo_id else None
        if processo is not None:
            verificar_acesso_processo(processo)
        processos = buscar_processos_resumo(db) if processo is None else None

        if request.method == "POST":
            id_processo = request.form.get("id_processo", type=int)
            nome_documento = request.form["nome_documento"].strip()
            tipo_documento = request.form.get("tipo_documento", "").strip()
            descricao = request.form.get("descricao", "").strip()
            processo_alvo = buscar_processo_ou_404(db, id_processo) if id_processo else None
            arquivo = request.files.get("arquivo")
            nome_original = secure_filename(arquivo.filename) if arquivo else ""

            erro = None
            if not id_processo or not nome_documento or processo_alvo is None:
                erro = "Informe o processo e o nome do documento."
            elif not arquivo or not nome_original:
                erro = "Selecione um arquivo para enviar."
            elif _extensao(nome_original) not in EXTENSOES_PERMITIDAS:
                erro = "Formato não suportado. Envie um arquivo PDF, DOC ou DOCX."
            elif _arquivo_vazio(arquivo):
                erro = "O arquivo selecionado está vazio."

            if erro:
                flash(erro, "erro")
            else:
                verificar_acesso_processo(processo_alvo)
                nome_arquivo, tamanho_bytes = _salvar_arquivo(arquivo, nome_original)
                cur = db.execute(
                    """
                    INSERT INTO documento
                        (id_processo, nome_documento, tipo_documento, descricao, data_upload,
                         id_usuario_upload, nome_arquivo, tamanho_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (id_processo, nome_documento, tipo_documento, descricao,
                     date.today().isoformat(), g.usuario["id"], nome_arquivo, tamanho_bytes),
                )
                registrar_log(
                    db, "criar", "documento", cur.lastrowid,
                    f"Documento '{nome_documento}' registrado no processo {processo_alvo['numero_processo']}.",
                )
                db.commit()
                flash("Documento registrado com sucesso.", "sucesso")
                return redirect(url_for("detalhe_processo", processo_id=id_processo, aba="documentos"))

        return render_template("documento_form.html", processo=processo, processos=processos, documento=None)

    @app.route("/documentos/<int:documento_id>/baixar")
    @login_required
    def baixar_documento(documento_id):
        db = db_module.get_db()
        documento = _buscar_documento_ou_404(db, documento_id)
        if documento is None or not documento["nome_arquivo"]:
            abort(404)
        verificar_acesso_processo(documento)
        extensao = _extensao(documento["nome_arquivo"])
        nome_download = f"{documento['nome_documento']}.{extensao}"
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"], documento["nome_arquivo"],
            as_attachment=extensao != "pdf", download_name=nome_download,
        )

    @app.route("/documentos/<int:documento_id>/editar", methods=["GET", "POST"])
    @login_required
    def editar_documento(documento_id):
        db = db_module.get_db()
        documento = _buscar_documento_ou_404(db, documento_id)
        if documento is None:
            return redirect(url_for("listar_documentos"))
        verificar_acesso_processo(documento)
        processo = buscar_processo_ou_404(db, documento["id_processo"])

        if request.method == "POST":
            nome_documento = request.form["nome_documento"].strip()
            tipo_documento = request.form.get("tipo_documento", "").strip()
            descricao = request.form.get("descricao", "").strip()
            arquivo = request.files.get("arquivo")
            nome_original = secure_filename(arquivo.filename) if arquivo and arquivo.filename else ""

            erro = None
            if not nome_documento:
                erro = "Informe o nome do documento."
            elif nome_original and _extensao(nome_original) not in EXTENSOES_PERMITIDAS:
                erro = "Formato não suportado. Envie um arquivo PDF, DOC ou DOCX."
            elif nome_original and _arquivo_vazio(arquivo):
                erro = "O arquivo selecionado está vazio."

            if erro:
                flash(erro, "erro")
            else:
                nome_arquivo = documento["nome_arquivo"]
                tamanho_bytes = documento["tamanho_bytes"]
                if nome_original:
                    novo_nome_arquivo, tamanho_bytes = _salvar_arquivo(arquivo, nome_original)
                    _remover_arquivo(nome_arquivo)
                    nome_arquivo = novo_nome_arquivo
                db.execute(
                    """
                    UPDATE documento
                    SET nome_documento = ?, tipo_documento = ?, descricao = ?,
                        nome_arquivo = ?, tamanho_bytes = ?
                    WHERE id = ?
                    """,
                    (nome_documento, tipo_documento, descricao, nome_arquivo, tamanho_bytes, documento_id),
                )
                registrar_log(
                    db, "editar", "documento", documento_id,
                    f"Documento '{nome_documento}' atualizado no processo {documento['numero_processo']}.",
                )
                db.commit()
                flash("Documento atualizado com sucesso.", "sucesso")
                return redirect(url_for(
                    "detalhe_processo", processo_id=documento["id_processo"], aba="documentos"
                ))

        return render_template(
            "documento_form.html", processo=processo, processos=None, documento=documento
        )

    @app.route("/documentos/<int:documento_id>/excluir", methods=["POST"])
    @login_required
    def excluir_documento(documento_id):
        db = db_module.get_db()
        documento = _buscar_documento_ou_404(db, documento_id)
        if documento is None:
            return redirect(url_for("listar_documentos"))
        verificar_acesso_processo(documento)
        _remover_arquivo(documento["nome_arquivo"])
        db.execute("DELETE FROM documento WHERE id = ?", (documento_id,))
        registrar_log(
            db, "excluir", "documento", documento_id,
            f"Documento '{documento['nome_documento']}' removido do processo {documento['numero_processo']}.",
        )
        db.commit()
        flash("Documento removido com sucesso.", "sucesso")
        return redirect(url_for(
            "detalhe_processo", processo_id=documento["id_processo"], aba="documentos"
        ))
