# -*- coding: utf-8 -*-
"""Popula o banco com dados FICTÍCIOS para fins didáticos (ver Seção 7 do enunciado).
Uso:
    python seed.py
"""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "instance" / "sistema.sqlite"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

ASSUNTOS = [
    "Cobrança de tributos municipais", "Reclamação trabalhista", "Ação de desapropriação",
    "Responsabilidade civil do Município", "Mandado de segurança", "Ação previdenciária de servidor",
    "Licitação e contrato administrativo", "Ação de improbidade administrativa",
    "Revisão de benefício de servidor", "Execução fiscal", "Ação civil pública ambiental",
    "Indenização por dano moral", "Contestação de multa administrativa", "Ação possessória",
]

PARTES = [
    "João da Silva", "Maria Oliveira Santos", "Pedro Henrique Souza", "Ana Paula Lima",
    "Carlos Eduardo Ferreira", "Fernanda Costa Ribeiro", "Rafael Almeida Nunes",
    "Juliana Martins Rocha", "Bruno Cardoso Teixeira", "Camila Barbosa Dias",
    "Lucas Gonçalves Pinto", "Patrícia Andrade Correia", "Diego Fernandes Araújo",
    "Beatriz Nascimento Cunha", "Thiago Moreira Castro",
]

COMARCAS = [
    "1ª Vara da Fazenda Pública", "2ª Vara Cível", "Vara do Trabalho",
    "Juizado Especial da Fazenda Pública", "Tribunal de Justiça – 2ª instância",
]

MOVIMENTACOES_EXEMPLO = [
    "Intimação recebida", "Petição protocolada", "Audiência realizada", "Despacho", "Decisão",
]

DOCUMENTOS_EXEMPLO = [
    ("Petição inicial", "Petição"), ("Intimação judicial", "Intimação"),
    ("Contestação", "Petição"), ("Decisão interlocutória", "Decisão"),
]


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def situacao_prazo_generator():
    hoje = date.today()
    # 2 vencidos, 8 próximos (<=5 dias), 5 confortáveis no futuro, 5 já cumpridos
    datas = []
    for i in range(2):
        datas.append((hoje - timedelta(days=3 + i * 4), False))
    for i in range(8):
        datas.append((hoje + timedelta(days=1 + i % 5), False))
    for i in range(5):
        datas.append((hoje + timedelta(days=20 + i * 7), False))
    for i in range(5):
        datas.append((hoje - timedelta(days=10 + i * 5), True))
    return datas


def main():
    conn = conectar()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # --- Usuários ---------------------------------------------------
    usuarios = [
        ("Administrador do Sistema", "admin", "admin123", "administrador", None),
        ("Dr. Carlos Oliveira", "carlos.oliveira", "adv12345", "advogado", "OAB/SP 000.001"),
        ("Dra. Juliana Souza", "juliana.souza", "adv12345", "advogado", "OAB/SP 000.002"),
        ("Dr. Marcos Pereira", "marcos.pereira", "adv12345", "advogado", "OAB/SP 000.003"),
    ]
    usuario_ids = []
    for nome, login, senha, tipo, oab in usuarios:
        cur = conn.execute(
            "INSERT INTO usuario (nome, login, senha_hash, tipo_usuario, oab, ativo) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (nome, login, generate_password_hash(senha), tipo, oab),
        )
        usuario_ids.append(cur.lastrowid)
    admin_id = usuario_ids[0]
    advogado_ids = usuario_ids[1:]

    # --- Processos ----------------------------------------------------
    # 50 processos: 35 em andamento, 13 encerrados, 1 aguardando providência, 1 aguardando decisão
    situacoes = (
        ["Em andamento"] * 35
        + ["Encerrado"] * 13
        + ["Aguardando providência"] * 1
        + ["Aguardando decisão"] * 1
    )
    hoje = date.today()
    processo_ids = []
    for i in range(50):
        numero = f"{1000 + i:07d}-{(i % 90) + 10:02d}.2026.8.00.0001"
        tipo = "Judicial" if i % 4 != 0 else "Administrativo"
        assunto = ASSUNTOS[i % len(ASSUNTOS)]
        parte = PARTES[i % len(PARTES)]
        comarca = COMARCAS[i % len(COMARCAS)]
        data_entrada = (hoje - timedelta(days=30 + i * 11)).isoformat()
        advogado_id = advogado_ids[i % len(advogado_ids)]
        situacao = situacoes[i]
        cur = conn.execute(
            """
            INSERT INTO processo
                (numero_processo, tipo, assunto, parte_principal, comarca_orgao,
                 data_entrada, id_advogado_responsavel, situacao, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (numero, tipo, assunto, parte, comarca, data_entrada, advogado_id, situacao,
             "Processo fictício gerado para fins didáticos."),
        )
        processo_ids.append(cur.lastrowid)

    # --- Prazos (20 no total, distribuídos entre os 15 primeiros processos ativos) ---
    ativos = [pid for pid, sit in zip(processo_ids, situacoes) if sit != "Encerrado"][:20]
    for (data_prazo, cumprido), processo_id in zip(situacao_prazo_generator(), ativos):
        responsavel_id = conn.execute(
            "SELECT id_advogado_responsavel FROM processo WHERE id = ?", (processo_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO prazo (id_processo, descricao, data_prazo, id_responsavel, cumprido) "
            "VALUES (?, ?, ?, ?, ?)",
            (processo_id, "Apresentar manifestação nos autos", data_prazo.isoformat(),
             responsavel_id, int(cumprido)),
        )

    # --- Movimentações (para os 12 primeiros processos) ---------------
    for idx, processo_id in enumerate(processo_ids[:12]):
        for j in range(2):
            data_mov = (hoje - timedelta(days=5 + idx * 3 + j * 2)).isoformat()
            descricao = MOVIMENTACOES_EXEMPLO[(idx + j) % len(MOVIMENTACOES_EXEMPLO)]
            usuario_reg = advogado_ids[idx % len(advogado_ids)]
            hora = f"{(9 + idx + j) % 18 + 8:02d}:{(idx * 7 + j * 13) % 60:02d}"
            conn.execute(
                "INSERT INTO movimentacao (id_processo, data, descricao, id_usuario_registro, hora_registro) "
                "VALUES (?, ?, ?, ?, ?)",
                (processo_id, data_mov, descricao, usuario_reg, hora),
            )

    # --- Documentos (para os 10 primeiros processos) -------------------
    for idx, processo_id in enumerate(processo_ids[:10]):
        nome_doc, tipo_doc = DOCUMENTOS_EXEMPLO[idx % len(DOCUMENTOS_EXEMPLO)]
        data_upload = (hoje - timedelta(days=8 + idx * 2)).isoformat()
        usuario_reg = advogado_ids[idx % len(advogado_ids)]
        conn.execute(
            """
            INSERT INTO documento
                (id_processo, nome_documento, tipo_documento, descricao, data_upload, id_usuario_upload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (processo_id, nome_doc, tipo_doc, "Documento fictício para fins de demonstração.",
             data_upload, usuario_reg),
        )

    # --- Configurações padrão ------------------------------------------
    conn.execute("INSERT INTO configuracao (chave, valor) VALUES ('nome_instituicao', 'Prefeitura Municipal')")
    conn.execute("INSERT INTO configuracao (chave, valor) VALUES ('nome_sistema', 'Gestão Jurídica Municipal')")
    conn.execute(
        "INSERT INTO configuracao (chave, valor) VALUES ('encarregado_nome', 'Dra. Renata Alvim (fictícia) — Encarregada de Dados')"
    )
    conn.execute(
        "INSERT INTO configuracao (chave, valor) VALUES ('encarregado_contato', 'encarregado.dados@prefeitura.exemplo.gov.br')"
    )

    conn.commit()
    conn.close()
    print("Banco de dados populado com dados fictícios em:", DB_PATH)
    print("Login administrador: admin / admin123")
    print("Login advogados: carlos.oliveira | juliana.souza | marcos.pereira  senha: adv12345")


if __name__ == "__main__":
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    main()
