from flask import g, render_template

import db as db_module
from helpers import prioridade_prazo, rotulo_relativo, status_prazo
from seguranca import eh_admin, login_required


def register(app):
    @app.route("/")
    @login_required
    def dashboard():
        db = db_module.get_db()
        restringir = not eh_admin()
        meu_id = g.usuario["id"]

        filtro_proc = " WHERE processo.id_advogado_responsavel = ?" if restringir else ""
        params_proc = [meu_id] if restringir else []

        total = db.execute(
            f"SELECT COUNT(*) AS n FROM processo{filtro_proc}", params_proc
        ).fetchone()["n"]
        em_andamento = db.execute(
            f"SELECT COUNT(*) AS n FROM processo{filtro_proc}"
            f"{' AND' if restringir else ' WHERE'} situacao = 'Em andamento'",
            params_proc,
        ).fetchone()["n"]
        encerrados = db.execute(
            f"SELECT COUNT(*) AS n FROM processo{filtro_proc}"
            f"{' AND' if restringir else ' WHERE'} situacao = 'Encerrado'",
            params_proc,
        ).fetchone()["n"]

        filtro_join = " AND processo.id_advogado_responsavel = ?" if restringir else ""

        prazos_abertos = db.execute(
            f"""
            SELECT prazo.data_prazo FROM prazo
            JOIN processo ON processo.id = prazo.id_processo
            WHERE prazo.cumprido = 0{filtro_join}
            """,
            params_proc,
        ).fetchall()
        proximos = vencidos = 0
        for p in prazos_abertos:
            rotulo, _ = status_prazo(p["data_prazo"], cumprido=False)
            if rotulo == "Vencido":
                vencidos += 1
            elif rotulo == "Próximo do vencimento":
                proximos += 1

        prioridades_rows = db.execute(
            f"""
            SELECT prazo.*, processo.numero_processo, processo.assunto, usuario.nome AS responsavel_nome
            FROM prazo
            JOIN processo ON processo.id = prazo.id_processo
            JOIN usuario ON usuario.id = prazo.id_responsavel
            WHERE prazo.cumprido = 0{filtro_join}
            ORDER BY prazo.data_prazo ASC
            LIMIT 6
            """,
            params_proc,
        ).fetchall()
        prioridades = []
        for p in prioridades_rows:
            rotulo, classe = prioridade_prazo(p["data_prazo"])
            prioridades.append({
                "processo_id": p["id_processo"], "numero_processo": p["numero_processo"],
                "assunto": p["assunto"], "responsavel_nome": p["responsavel_nome"],
                "prazo_label": rotulo_relativo(p["data_prazo"]), "rotulo": rotulo, "classe": classe,
            })

        ultimas_movimentacoes = db.execute(
            f"""
            SELECT movimentacao.*, processo.numero_processo, usuario.nome AS usuario_nome
            FROM movimentacao
            JOIN processo ON processo.id = movimentacao.id_processo
            JOIN usuario ON usuario.id = movimentacao.id_usuario_registro
            {'WHERE processo.id_advogado_responsavel = ?' if restringir else ''}
            ORDER BY movimentacao.data DESC, movimentacao.id DESC
            LIMIT 6
            """,
            params_proc,
        ).fetchall()

        primeiro_nome = g.usuario["nome"].replace("Dr.", "").replace("Dra.", "").strip().split()[0]

        return render_template(
            "dashboard.html",
            primeiro_nome=primeiro_nome,
            total=total, em_andamento=em_andamento, encerrados=encerrados,
            proximos=proximos, vencidos=vencidos,
            prioridades=prioridades,
            ultimas_movimentacoes=ultimas_movimentacoes,
        )
