# Sistema de Gestão de Processos Jurídicos Municipais

Protótipo funcional de um sistema web para apoiar o setor jurídico de uma Prefeitura Municipal
no controle de processos judiciais e administrativos, prazos, movimentações e documentos —
substituindo o controle manual hoje feito por planilhas eletrônicas.

Trabalho acadêmico desenvolvido para a disciplina de Legislação e Ética do curso de Engenharia
de Software, com foco não apenas na implementação técnica, mas também na aplicação de conceitos
de **LGPD**, **ética profissional** e **segurança da informação** ao longo de todo o projeto.

> **Dados fictícios.** Todo o conteúdo de exemplo (processos, partes, advogados, documentos) é
> fictício e usado exclusivamente para fins didáticos. Nenhuma informação real de processo,
> cidadão, servidor público ou órgão foi utilizada.

## Funcionalidades

- **Login e perfis de acesso** — dois tipos de usuário (Administrador e Advogado/Procurador),
  cada um com permissões próprias. Um advogado só acessa os processos sob sua responsabilidade.
- **Processos** — cadastro, edição, exclusão e consulta (com busca por número, parte, advogado
  responsável e situação).
- **Prazos** — cadastro, edição, exclusão e marcação como cumprido, com destaque automático por
  urgência (vencido / próximo do vencimento / no prazo).
- **Movimentações** — histórico cronológico de eventos de cada processo (petição protocolada,
  audiência, decisão, sentença etc.), com autor e data/hora de cada registro.
- **Documentos** — upload real de arquivos PDF, DOC e DOCX vinculados a um processo, com
  download, edição e exclusão.
- **Dashboard** — indicadores gerais do setor (processos cadastrados, em andamento, encerrados,
  prazos próximos e vencidos) e a lista de prioridades do dia.
- **Usuários** — gestão de contas pelo Administrador: criação, edição, redefinição de senha e
  ativação/desativação.
- **Auditoria** — registro (log) de quem realizou cada operação de criação, edição, exclusão e
  login, com data e hora, consultável pelo Administrador.
- **Política de Privacidade** — página pública com as informações do Encarregado de Dados (DPO),
  em atendimento ao art. 41 da LGPD.

## Segurança

- Senhas armazenadas com hash criptográfico (nunca em texto plano).
- Proteção contra CSRF em todos os formulários.
- Controle de acesso por perfil de usuário, inclusive por registro individual (um advogado não
  acessa dados de processos de outro advogado).
- Bloqueio temporário de conta após tentativas repetidas de login incorretas.
- Cabeçalhos HTTP de segurança (proteção contra clickjacking e cache de páginas autenticadas).
- Log de auditoria de todas as operações relevantes, incluindo tentativas de login malsucedidas.

## Tecnologias

- **Python 3** + **Flask** — backend e roteamento.
- **SQLite** — banco de dados local, sem necessidade de servidor externo.
- **Jinja2** — templates HTML renderizados no servidor.
- HTML, CSS e JavaScript simples no frontend, sem frameworks externos.

## Como executar

Pré-requisitos: Python 3.10+ instalado.

```bash
cd sistema
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# cria o banco de dados e popula com dados fictícios de exemplo
python seed.py

# inicia o servidor
python app.py
```

O sistema fica disponível em `http://localhost:5000`.

Usuários de exemplo criados pelo `seed.py`:

| Perfil               | Login             | Senha      |
|-----------------------|-------------------|------------|
| Administrador          | `admin`           | `admin123` |
| Advogado/Procurador    | `carlos.oliveira` | `adv12345` |
| Advogado/Procurador    | `juliana.souza`   | `adv12345` |
| Advogado/Procurador    | `marcos.pereira`  | `adv12345` |

## Estrutura do projeto

```
sistema/
├── app.py            # criação da aplicação Flask, configuração e hooks globais
├── db.py             # conexão com o banco de dados SQLite
├── csrf.py           # proteção CSRF
├── seguranca.py       # autenticação, controle de acesso e permissões
├── helpers.py         # filtros de template e funções auxiliares
├── schema.sql         # definição das tabelas do banco de dados
├── seed.py            # geração de dados fictícios de exemplo
├── routes/            # uma rota por módulo (processos, prazos, movimentações, documentos...)
├── templates/          # páginas HTML (Jinja2)
└── static/             # CSS e JavaScript
```
