"""Filtros Jinja, utilitários de data e consultas de domínio usados por várias rotas."""
from datetime import date, datetime

from flask import flash, g

from seguranca import eh_admin

PRAZO_ALERTA_DIAS = 5  # a partir de quantos dias de antecedência um prazo é "próximo do vencimento"

SITUACOES_PROCESSO = ["Em andamento", "Aguardando providência", "Aguardando decisão", "Encerrado"]

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CONFIG_PADRAO = {
    "nome_instituicao": "Prefeitura Municipal",
    "nome_sistema": "Gestão Jurídica Municipal",
    "encarregado_nome": "A definir pela Prefeitura (art. 41 da LGPD)",
    "encarregado_contato": "encarregado.dados@prefeitura.exemplo.gov.br",
}

SITUACAO_CLASSES = {
    "Em andamento": "situacao-em-andamento",
    "Aguardando providência": "situacao-aguardando-providencia",
    "Aguardando decisão": "situacao-aguardando-decisao",
    "Encerrado": "situacao-encerrado",
}


def situacao_classe(situacao):
    return SITUACAO_CLASSES.get(situacao, "")


ACAO_LABELS = {
    "login": "Login",
    "login_falho": "Login malsucedido",
    "criar": "Criação",
    "editar": "Edição",
    "excluir": "Exclusão",
}

ACAO_CLASSES = {
    "login": "status-no-prazo",
    "login_falho": "status-vencido",
    "criar": "status-no-prazo",
    "editar": "status-proximo",
    "excluir": "status-vencido",
}

ENTIDADE_LABELS = {
    "usuario": "Usuário",
    "processo": "Processo",
    "prazo": "Prazo",
    "movimentacao": "Movimentação",
    "documento": "Documento",
    "configuracao": "Configuração",
}


def rotulo_acao(acao):
    return ACAO_LABELS.get(acao, acao)


def classe_acao(acao):
    return ACAO_CLASSES.get(acao, "")


def rotulo_entidade(entidade):
    return ENTIDADE_LABELS.get(entidade, entidade)


def extensao_documento(nome_arquivo):
    if not nome_arquivo or "." not in nome_arquivo:
        return "?"
    return nome_arquivo.rsplit(".", 1)[-1].upper()


def formatar_tamanho(tamanho_bytes):
    if not tamanho_bytes:
        return ""
    if tamanho_bytes < 1024 * 1024:
        return f"{max(1, round(tamanho_bytes / 1024))} KB"
    return f"{tamanho_bytes / (1024 * 1024):.1f} MB"


def iniciais(nome):
    if not nome:
        return "?"
    partes = [p for p in nome.replace(".", " ").split() if p.lower() not in ("dr", "dra")]
    if not partes:
        partes = nome.split()
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------

def parse_data(valor):
    return datetime.strptime(valor, "%Y-%m-%d").date()


def formatar_data_extenso(data_str, com_ano=True):
    d = parse_data(data_str)
    texto = f"{d.day:02d} {MESES_PT[d.month - 1]}"
    return f"{texto} {d.year}" if com_ano else texto


def formatar_datahora(iso_str):
    if not iso_str:
        return None
    dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S")
    return f"{dt.day:02d} {MESES_PT[dt.month - 1]} {dt.year} · {dt.strftime('%H:%M')}"


def rotulo_relativo(data_str):
    d = parse_data(data_str)
    dias = (d - date.today()).days
    if dias == 0:
        return "Hoje"
    if dias == 1:
        return "Amanhã"
    return formatar_data_extenso(data_str, com_ano=False)


def status_prazo(data_prazo_str, cumprido):
    """Rótulo/classe usados nas telas de detalhe e na página de Prazos."""
    if cumprido:
        return "Cumprido", "status-cumprido"
    dias = (parse_data(data_prazo_str) - date.today()).days
    if dias < 0:
        return "Vencido", "status-vencido"
    if dias <= PRAZO_ALERTA_DIAS:
        return "Próximo do vencimento", "status-proximo"
    return "No prazo", "status-no-prazo"


def prioridade_prazo(data_prazo_str):
    """Rótulo/classe usados na lista 'Prioridades de hoje' do dashboard."""
    dias = (parse_data(data_prazo_str) - date.today()).days
    if dias <= 0:
        return "Urgente", "status-vencido"
    if dias <= PRAZO_ALERTA_DIAS:
        return "Próximo", "status-proximo"
    return "No prazo", "status-no-prazo"


# ---------------------------------------------------------------------------
# Consultas de domínio
# ---------------------------------------------------------------------------

def buscar_advogados(db, incluir_inativo_id=None):
    """Advogados ativos para os seletores de formulário.

    `incluir_inativo_id` mantém na lista o advogado atualmente responsável mesmo se
    ele tiver sido desativado, para que editar um processo dele não o reatribua
    silenciosamente a outra pessoa (o `<select>` precisa da opção correspondente).
    """
    if incluir_inativo_id:
        return db.execute(
            "SELECT id, nome, ativo FROM usuario "
            "WHERE tipo_usuario = 'advogado' AND (ativo = 1 OR id = ?) "
            "ORDER BY ativo DESC, nome",
            (incluir_inativo_id,),
        ).fetchall()
    return db.execute(
        "SELECT id, nome, ativo FROM usuario WHERE tipo_usuario = 'advogado' AND ativo = 1 ORDER BY nome"
    ).fetchall()


def buscar_processos_resumo(db):
    """Processos para seletor de formulário — restrito aos próprios quando o usuário é advogado."""
    if eh_admin():
        return db.execute(
            "SELECT id, numero_processo, assunto FROM processo ORDER BY data_entrada DESC"
        ).fetchall()
    return db.execute(
        "SELECT id, numero_processo, assunto FROM processo "
        "WHERE id_advogado_responsavel = ? ORDER BY data_entrada DESC",
        (g.usuario["id"],),
    ).fetchall()


def buscar_processo_ou_404(db, processo_id):
    processo = db.execute(
        """
        SELECT processo.*, usuario.nome AS advogado_nome
        FROM processo
        JOIN usuario ON usuario.id = processo.id_advogado_responsavel
        WHERE processo.id = ?
        """,
        (processo_id,),
    ).fetchone()
    if processo is None:
        flash("Processo não encontrado.", "erro")
    return processo


def buscar_configuracao(db):
    linhas = db.execute("SELECT chave, valor FROM configuracao").fetchall()
    config = dict(CONFIG_PADRAO)
    config.update({linha["chave"]: linha["valor"] for linha in linhas})
    return config


# ---------------------------------------------------------------------------
# Auditoria (LGPD arts. 37 e 46-49)
# ---------------------------------------------------------------------------

def registrar_log(db, acao, entidade, entidade_id=None, descricao=None, usuario=None):
    """Grava uma linha no log de auditoria com autor e data/hora.

    `usuario` é opcional para permitir registrar tentativas de login sem
    usuário autenticado em g; nos demais casos usa g.usuario.
    """
    usuario = usuario if usuario is not None else g.get("usuario")
    db.execute(
        "INSERT INTO log_auditoria (id_usuario, usuario_nome, acao, entidade, entidade_id, descricao, data_hora) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            usuario["id"] if usuario else None,
            usuario["nome"] if usuario else "(login não identificado)",
            acao, entidade, entidade_id, descricao,
            datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        ),
    )
