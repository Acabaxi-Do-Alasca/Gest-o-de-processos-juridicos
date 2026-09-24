DROP TABLE IF EXISTS log_auditoria;
DROP TABLE IF EXISTS documento;
DROP TABLE IF EXISTS movimentacao;
DROP TABLE IF EXISTS prazo;
DROP TABLE IF EXISTS processo;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS configuracao;

CREATE TABLE usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    tipo_usuario TEXT NOT NULL CHECK (tipo_usuario IN ('administrador', 'advogado')),
    oab TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    ultimo_acesso TEXT,
    tentativas_falhas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT
);

CREATE TABLE configuracao (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE processo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_processo TEXT NOT NULL,
    tipo TEXT NOT NULL,
    assunto TEXT NOT NULL,
    parte_principal TEXT NOT NULL,
    comarca_orgao TEXT NOT NULL,
    data_entrada TEXT NOT NULL,
    id_advogado_responsavel INTEGER NOT NULL REFERENCES usuario(id),
    situacao TEXT NOT NULL DEFAULT 'Em andamento'
        CHECK (situacao IN ('Em andamento', 'Aguardando providência', 'Aguardando decisão', 'Encerrado')),
    observacoes TEXT
);

CREATE TABLE prazo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_processo INTEGER NOT NULL REFERENCES processo(id),
    descricao TEXT NOT NULL,
    data_prazo TEXT NOT NULL,
    id_responsavel INTEGER NOT NULL REFERENCES usuario(id),
    cumprido INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE movimentacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_processo INTEGER NOT NULL REFERENCES processo(id),
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    id_usuario_registro INTEGER NOT NULL REFERENCES usuario(id),
    hora_registro TEXT
);

CREATE TABLE documento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_processo INTEGER NOT NULL REFERENCES processo(id),
    nome_documento TEXT NOT NULL,
    tipo_documento TEXT,
    descricao TEXT,
    data_upload TEXT NOT NULL,
    id_usuario_upload INTEGER NOT NULL REFERENCES usuario(id),
    nome_arquivo TEXT,
    tamanho_bytes INTEGER,
    id_movimentacao INTEGER REFERENCES movimentacao(id),
    id_prazo INTEGER REFERENCES prazo(id)
);

-- Registro de auditoria (LGPD arts. 37 e 46-49; item "Segurança" do enunciado):
-- toda criação, alteração e exclusão relevante gera uma linha aqui, com autor e data/hora,
-- permitindo apurar responsabilidade em caso de uso indevido dos dados dos processos.
CREATE TABLE log_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER REFERENCES usuario(id),
    usuario_nome TEXT NOT NULL,
    acao TEXT NOT NULL CHECK (acao IN ('login', 'login_falho', 'criar', 'editar', 'excluir')),
    entidade TEXT NOT NULL CHECK (entidade IN ('usuario', 'processo', 'prazo', 'movimentacao', 'documento', 'configuracao')),
    entidade_id INTEGER,
    descricao TEXT,
    data_hora TEXT NOT NULL
);

CREATE INDEX idx_processo_advogado ON processo(id_advogado_responsavel);
CREATE INDEX idx_prazo_processo ON prazo(id_processo);
CREATE INDEX idx_movimentacao_processo ON movimentacao(id_processo);
CREATE INDEX idx_documento_processo ON documento(id_processo);
CREATE INDEX idx_log_entidade ON log_auditoria(entidade, entidade_id);
CREATE INDEX idx_log_data ON log_auditoria(data_hora DESC);
