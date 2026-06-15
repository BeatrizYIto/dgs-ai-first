# Tasks — Query Endpoint

Derivadas do [plan.md](plan.md).

---

## T001 — Implementar utilitário de retry com exponential backoff

**Estimativa:** P

**Descrição:**  
Criar função genérica `withRetry<T>(fn, options)` em `src/lib/retry.ts` que aplica exponential backoff para chamadas que lançam erros transientes. Configurável: tentativas máximas, delay base, jitter.

**Critérios de aceite:**
- Retenta apenas em erros com status 429 / 5xx (outros relançam imediatamente)
- Delay cresce exponencialmente a cada tentativa com jitter aleatório
- Número máximo de tentativas respeitado; após esgotamento relança o último erro
- Testes unitários cobrem: sucesso na 1ª tentativa, sucesso após retry, falha após N tentativas

**Dependências:** nenhuma

---

## T002 — Configurar logging estruturado com Pino

**Estimativa:** P

**Descrição:**  
Criar instância compartilhada de logger em `src/lib/logger.ts` usando Pino. Logger deve emitir JSON estruturado em produção e output legível (`pino-pretty`) em desenvolvimento.

**Critérios de aceite:**
- `NODE_ENV=production` → saída JSON em uma linha por evento
- `NODE_ENV=development` → saída colorida e formatada via `pino-pretty`
- Logger exportado como singleton reutilizável por todos os módulos
- Nenhum `console.log` presente fora de `logger.ts`

**Dependências:** nenhuma

---

## T003 — Definir e validar schema de input com Zod

**Estimativa:** P

**Descrição:**  
Criar schema Zod em `src/schemas/query.ts` para o body do POST `/api/query`. Campo obrigatório: `question` (string, não vazia, máx. 1000 chars). Exportar tipo TypeScript derivado do schema.

**Critérios de aceite:**
- Requisição sem `question` retorna 400 com mensagem de erro descritiva
- `question` vazia ou acima de 1000 chars retorna 400
- Campos extras são ignorados (`.strip()`)
- Tipo `QueryInput` inferido do schema está disponível para importação

**Dependências:** nenhuma

---

## T004 — Implementar cliente Azure OpenAI para geração de embeddings

**Estimativa:** M

**Descrição:**  
Criar módulo `src/services/embeddings.ts` que recebe uma string e retorna o vetor de embedding usando o deployment configurado no Azure OpenAI. Utilizar `withRetry` para resiliência.

**Critérios de aceite:**
- Variáveis de ambiente necessárias: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- Ausência de qualquer variável lança erro descritivo na inicialização
- Retorna `number[]` com a dimensão correta para o modelo configurado
- Falhas transientes são retentadas via `withRetry`; falhas permanentes são relançadas
- Log de duração da chamada emitido via Pino

**Dependências:** T001, T002

---

## T005 — Implementar busca top-5 no Azure AI Search

**Estimativa:** M

**Descrição:**  
Criar módulo `src/services/search.ts` que recebe um vetor de embedding e retorna os 5 chunks mais relevantes do índice Azure AI Search, incluindo `content` e `source_document` de cada chunk.

**Critérios de aceite:**
- Variáveis de ambiente necessárias: `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, `AZURE_SEARCH_INDEX_NAME`
- Retorna array de até 5 objetos `{ content: string; source_document: string }`
- Busca usa vetor (vector search) — não busca textual simples
- Falhas transientes retentadas via `withRetry`
- Log com número de resultados retornados emitido via Pino

**Dependências:** T001, T002

---

## T006 — Implementar montagem do prompt respeitando context budget

**Estimativa:** M

**Descrição:**  
Criar função `buildPrompt` em `src/lib/prompt.ts` que recebe os chunks do Search e a pergunta do usuário, lê o system prompt de `/prompts/system-prompt.md` e monta o array de mensagens para o GPT-4o respeitando o budget: ~4K tokens para system prompt, ~8K tokens para chunks, restante para a pergunta.

**Critérios de aceite:**
- System prompt lido do arquivo em tempo de inicialização (não a cada chamada)
- Chunks truncados ou removidos se ultrapassarem ~8K tokens; chunks priorizados por score de relevância
- Pergunta incluída integralmente; se exceder o espaço restante, retorna erro descritivo
- Função pura e testável (sem I/O exceto leitura inicial do arquivo)
- Testes unitários validam: montagem padrão, truncamento de chunks, pergunta dentro do limite

**Dependências:** T003, T004, T005

---

## T007 — Implementar chamada ao GPT-4o e formatar resposta

**Estimativa:** M

**Descrição:**  
Criar módulo `src/services/completion.ts` que recebe o array de mensagens montado por `buildPrompt`, envia ao deployment GPT-4o no Azure OpenAI e retorna `{ answer: string; source_document: string }` com o nome do documento de maior relevância.

**Critérios de aceite:**
- Variável de ambiente necessária: `AZURE_OPENAI_COMPLETION_DEPLOYMENT`
- `source_document` extraído do chunk de maior score retornado pelo Search
- Falhas transientes retentadas via `withRetry`
- Log com tokens utilizados (`prompt_tokens`, `completion_tokens`) emitido via Pino
- Resposta vazia do modelo lança erro descritivo

**Dependências:** T001, T002, T006

---

## T008 — Definir e validar schema de output com Zod

**Estimativa:** P

**Descrição:**  
Criar schema Zod em `src/schemas/query.ts` (mesmo arquivo do input) para a resposta da API: `{ answer: string; source_document: string }`. Validar a saída antes de enviar ao cliente.

**Critérios de aceite:**
- Schema valida que `answer` e `source_document` são strings não vazias
- Se a resposta interna não passar na validação, a função retorna 500 com log de erro (sem vazar detalhes internos)
- Tipo `QueryOutput` inferido do schema está disponível para importação

**Dependências:** T007

---

## T009 — Implementar HTTP trigger POST /api/query (wiring completo)

**Estimativa:** M

**Descrição:**  
Criar a Azure Function em `src/functions/query.ts` que orquestra todo o fluxo: valida input → gera embedding → busca chunks → monta prompt → chama GPT-4o → valida output → retorna resposta. Retornar códigos HTTP apropriados para cada tipo de falha.

**Critérios de aceite:**
- `POST /api/query` com body válido retorna 200 `{ answer, source_document }`
- Input inválido retorna 400 com descrição do erro de validação
- Erros internos retornam 500 com mensagem genérica (sem stack trace no body)
- Todas as etapas do fluxo logadas com Pino (correlacionadas por request ID)
- Função registrada no host e acessível via `func start`

**Dependências:** T002, T003, T006, T007, T008

---

## T010 — Testes de integração do endpoint /api/query

**Estimativa:** G

**Descrição:**  
Escrever testes de integração (usando Azure Functions test runner ou vitest com mocks de serviços externos) que cobrem o fluxo completo do endpoint, incluindo cenários de erro.

**Critérios de aceite:**
- Cenário feliz: pergunta válida → 200 com `answer` e `source_document`
- Input inválido (sem `question`) → 400
- Falha no Azure OpenAI (mock) → 500 com mensagem genérica
- Falha no Azure AI Search (mock) → 500 com mensagem genérica
- Nenhum segredo real usado nos testes (variáveis mockadas)
- Todos os testes passam em `npm test` sem dependência de infra externa

**Dependências:** T009

---

## Resumo de dependências

```
T001 ──┐
T002 ──┤
T003 ──┤
       ├── T004
       ├── T005
       └── T006
             └── T007
                   └── T008
                         └── T009
                               └── T010
```
