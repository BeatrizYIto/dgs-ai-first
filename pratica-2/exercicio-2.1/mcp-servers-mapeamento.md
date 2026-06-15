# Mapeamento: Necessidades do Projeto → MCP Reference Servers

## 1. Código, specs e skills (ler e escrever)

**Servidor:** `@modelcontextprotocol/server-filesystem` — instância `repo-source`

| | |
|---|---|
| **Escopo** | `./src`, `./specs`, `./skills`, `./prompts` |
| **Tools expostos** | `read_file`, `write_file`, `create_directory`, `list_directory`, `move_file`, `search_files`, `get_file_info` |
| **Resources** | `file://<path>` para qualquer arquivo dentro dos diretórios permitidos |
| **Quem consome** | Claude Code (edição ativa), agente de geração de código, agente de review de specs |
| **Por que esse** | É o único servidor que permite escrita — essencial para criar/editar código e skills |

---

## 2. Documentação de negócio NovaTech (somente ler)

**Servidor:** `@modelcontextprotocol/server-filesystem` — instância `novatech-docs`

| | |
|---|---|
| **Escopo** | `./docs/novatech/` (contém FAQ, POL-001, PROC-042, SLA-2024) |
| **Tools expostos** | `read_file`, `list_directory`, `search_files` — sem `write_file` no escopo |
| **Resources** | `file://docs/novatech/<doc>.md` como recurso consultável |
| **Quem consome** | Agente de RAG/query-endpoint, bot Teams, pipeline de ingestão ao detectar novos docs |
| **Por que instância separada** | Isolar o escopo impede que o agente escreva por engano em docs de política; escopo mínimo = superfície mínima de risco |

---

## 3. Corpus de chunks para recuperação (somente ler)

**Servidor:** `@modelcontextprotocol/server-filesystem` — instância `retrieval-corpus`

| | |
|---|---|
| **Escopo** | `./data/retrieval-corpus/` (contém `chunks-novatech.md`) |
| **Tools expostos** | `read_file`, `list_directory`, `search_files` |
| **Resources** | `file://data/retrieval-corpus/chunks-novatech.md` |
| **Quem consome** | Query-endpoint (busca de chunks relevantes antes de montar o prompt), avaliador de evals |
| **Por que esse** | O corpus é lido por arquivo; `search_files` permite busca textual sem vetorstore externo — suficiente para MVP |

---

## 4. Histórico e branches do repositório

**Servidor:** `mcp-server-git` (pacote PyPI via `uvx`)

| | |
|---|---|
| **Escopo** | `--repository .` (raiz do repo `novatech-assistant/`) |
| **Tools expostos** | `git_log`, `git_diff`, `git_status`, `git_show`, `git_branch`, `git_create_branch`, `git_checkout`, `git_commit`, `git_add` |
| **Resources** | `git://<repo>/commits/<hash>` — histórico de commits como recurso navegável |
| **Quem consome** | Claude Code (contexto de mudanças em andamento), agente de code-review, agente de changelog |
| **Por que esse** | Filesystem não enxerga histórico Git; só o `mcp-server-git` expõe `git_log`/`git_diff` como tools MCP estruturadas |

---

## 5. Memória persistente — decisões e linguagem ubíqua

**Servidor:** `@modelcontextprotocol/server-memory`

| | |
|---|---|
| **Escopo** | Sem path de arquivo — persiste em grafo de conhecimento (JSON interno) |
| **Tools expostos** | `create_entities`, `create_relations`, `add_observations`, `search_nodes`, `open_nodes`, `delete_entities`, `delete_relations` |
| **Resources** | `memory://entities` — grafo navegável de entidades e relações |
| **Prompts** | Nenhum nativo; a linguagem ubíqua entra como entidades + observações via `create_entities` |
| **Quem consome** | **Todos os agentes** — grounding de termos do domínio (ex: "Pedido Especial", "SLA Nível 2"), decisões arquiteturais (ADRs resumidos), glossário da NovaTech |
| **Por que esse** | O grafo de entidades persiste entre sessões; qualquer agente pode consultar `search_nodes("devolução")` e recuperar a política vigente sem reler todos os docs |

---

## Sobre o `server-everything`

O `server-everything` **não mapeia a nenhuma das 5 necessidades de produção** — ele é um servidor de referência/demo que expõe todos os primitivos MCP (tools echo/add, resources text/blob, prompts, sampling) para **validar que a conectividade MCP está funcionando** antes de ligar os servidores reais. Use durante o setup inicial para confirmar que o Claude Code consegue chamar tools MCP; retire depois.

---

## Resumo

| Necessidade | Servidor | Escopo | Acesso |
|---|---|---|---|
| Código / specs / skills | `filesystem` (repo-source) | `./src` `./specs` `./skills` `./prompts` | R+W |
| Docs NovaTech | `filesystem` (novatech-docs) | `./docs/novatech/` | R |
| Corpus de chunks | `filesystem` (retrieval-corpus) | `./data/retrieval-corpus/` | R |
| Histórico / branches | `mcp-server-git` | `.` (repo root) | R+W git |
| Memória / ubíqua | `server-memory` | grafo em memória | R+W |
