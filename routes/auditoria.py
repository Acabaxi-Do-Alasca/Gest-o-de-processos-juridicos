from flask import render_template, request

import db as db_module
from seguranca import admin_required

PAGINA_TAMANHO = 50


def register(app):
    @app.route("/auditoria")
    @admin_required
    def listar_auditoria():
        db = db_module.get_db()
        entidade = request.args.get("entidade", "").strip()
        pagina = max(1, request.args.get("pagina", 1, type=int))

        condicoes = []
        parametros = []
        if entidade:
            condicoes.append("entidade = ?")
            parametros.append(entidade)

        sql = "SELECT * FROM log_auditoria"
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        parametros += [PAGINA_TAMANHO + 1, (pagina - 1) * PAGINA_TAMANHO]

        registros = db.execute(sql, parametros).fetchall()
        tem_proxima = len(registros) > PAGINA_TAMANHO
        registros = registros[:PAGINA_TAMANHO]
        return render_template(
            "auditoria_list.html", registros=registros, filtro_entidade=entidade,
            pagina=pagina, tem_proxima=tem_proxima,
        )
