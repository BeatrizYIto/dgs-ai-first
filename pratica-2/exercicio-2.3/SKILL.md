# TypeScript Conventions

> **Escopo:** todo arquivo `.ts` e `.tsx` do repositório — backend, serviços, schemas, pipeline, bot e web.  
> **Pré-requisito para:** todas as outras skills. Leia antes de qualquer geração de código.

---

## Contexto

O NovaTech Assistant roda em Azure Functions v4 com Node.js 20. O runtime usa **ESM puro** (`"type": "module"` no `package.json`), o que muda como o Node resolve importações em relação ao CommonJS clássico. Além disso, toda entrada externa (HTTP body, variáveis de ambiente, resposta da IA) passa por validação com **Zod** antes de chegar ao código de negócio.

Essas convenções existem por três razões objetivas:
1. **Evitar quebras silenciosas em tempo de execução** — erros de import ESM só aparecem em runtime; não há aviso em compile-time.
2. **Fechar a superfície de bugs de tipo** — `unknown` + Zod garante que nenhum dado externo entra sem validação.
3. **Uniformidade para Claude Code** — nomes e estrutura previsíveis permitem que o assistente navegue e gere código sem ambiguidade.

---

## Regras prescritivas

### R1 — Use `.js` em todos os caminhos de import

O compilador TypeScript emite `.js`, e o Node ESM resolve `.js`. Escreva a extensão no `import` mesmo que o arquivo-fonte seja `.ts`.

```typescript
// ✅ DO
import { logger } from "../shared/logger.js";
import { SearchError } from "../shared/errors.js";
import { InputSchema } from "../../schemas/query.js";

// ❌ DON'T — quebra em runtime no modo ESM
import { logger } from "../shared/logger";
import { SearchError } from "../shared/errors";
```

### R2 — `unknown` para dados externos; nunca `any`

Use `unknown` para qualquer valor que vem de fora do código (HTTP body, resposta de API, `process.env`). Narrow com Zod antes de usar.

```typescript
// ✅ DO
export async function handler(request: HttpRequest): Promise<HttpResponseInit> {
  const body: unknown = await request.json();
  const input = InputSchema.parse(body); // narrow para o tipo correto
}

// ❌ DON'T — perde a proteção de tipo
export async function handler(request: HttpRequest): Promise<HttpResponseInit> {
  const body: any = await request.json();
  const question = body.question; // acesso não validado
}
```

### R3 — Zod como fronteira obrigatória de validação

Todo dado externo deve passar por um schema Zod antes de ser usado. Use `parse` em serviços (lança exceção em falha) e `safeParse` em handlers HTTP (permite retornar 400 sem try/catch).

```typescript
// ✅ DO — handler HTTP: safeParse para controlar o fluxo de erro
const result = InputSchema.safeParse(body);
if (!result.success) {
  return { status: 400, jsonBody: { error: result.error.flatten() } };
}
const { question } = result.data;

// ✅ DO — serviço interno: parse propaga a exceção para o handler
const validated = OutputSchema.parse(rawAiResponse);

// ❌ DON'T — validação manual sem Zod
if (typeof body.question !== "string" || body.question.length === 0) { ... }
```

### R4 — `satisfies` para literais com tipo esperado

Use `satisfies` ao declarar objetos literais que precisam respeitar um contrato de tipo sem perder a inferência do literal.

```typescript
// ✅ DO — inferência mantida; erro se campo faltando
const config = {
  logLevel: "info",
  maxTokens: 8192,
} satisfies AppConfig;

// ❌ DON'T — anotação direta perde a inferência do literal
const config: AppConfig = {
  logLevel: "info",
  maxTokens: 8192,
};
```

### R5 — Sempre `async/await`; nunca `.then()/.catch()` encadeados

```typescript
// ✅ DO
const results = await searchClient.search(query);
const answer  = await openai.complete(prompt);

// ❌ DON'T
searchClient.search(query)
  .then((results) => openai.complete(buildPrompt(results)))
  .then((answer) => resolve(answer))
  .catch((err) => reject(err));
```

### R6 — Nunca engolir erros com `catch` vazio

```typescript
// ✅ DO — propague ou envolva em erro de domínio
try {
  return await searchClient.search(query);
} catch (err) {
  throw new SearchError("Azure AI Search falhou", "SEARCH_ERROR");
}

// ❌ DON'T — falha silenciosa, estado indefinido
try {
  return await searchClient.search(query);
} catch { }
```

### R7 — Nenhum `index.ts` barrel; importe o arquivo diretamente

```typescript
// ✅ DO
import { buildPrompt } from "../services/prompt-builder.js";

// ❌ DON'T — barrel cria acoplamento implícito e dificulta tree-shaking
import { buildPrompt } from "../services/index.js";
```

### R8 — Convenções de nomenclatura

| Entidade | Convenção | Exemplo |
|----------|-----------|---------|
| Tipos, interfaces, classes | `PascalCase` | `SearchResult`, `QueryInput`, `NovaTechError` |
| Funções, variáveis, parâmetros | `camelCase` | `searchChunks`, `requestId`, `durationMs` |
| Constantes de módulo | `UPPER_SNAKE_CASE` | `MAX_CHUNK_TOKENS`, `DEFAULT_TOP_K` |
| Nomes de arquivo | `kebab-case.ts` | `prompt-builder.ts`, `query-handler.ts` |
| Schemas Zod | sufixo `Schema` | `InputSchema`, `OutputSchema`, `EnvSchema` |

---

## Exemplos concretos (DO / DON'T)

### Módulo de serviço completo

```typescript
// ✅ DO — src/services/search.ts
import { SearchClient } from "@azure/search-documents";
import { RestError } from "@azure/core-rest-pipeline";
import { config } from "../shared/config.js";
import { logger } from "../shared/logger.js";
import { SearchError } from "../shared/errors.js";
import type { SearchResult } from "../shared/types.js";

export async function searchChunks(
  embedding: number[],
  requestId: string
): Promise<SearchResult[]> {
  const client = new SearchClient(
    config.AZURE_SEARCH_ENDPOINT,
    config.AZURE_SEARCH_INDEX_NAME,
    { key: config.AZURE_SEARCH_API_KEY }
  );

  try {
    const results = await client.search("*", {
      vectorSearchOptions: { queries: [{ vector: embedding, fields: ["contentVector"], kNearestNeighborsCount: 5 }] },
    });

    const chunks: SearchResult[] = [];
    for await (const r of results.results) {
      chunks.push(r.document as SearchResult);
    }

    logger.info({ requestId, operation: "searchChunks", count: chunks.length }, "Search complete");
    return chunks;
  } catch (err) {
    if (err instanceof RestError) {
      throw new SearchError(`Azure AI Search falhou (${err.statusCode})`, "SEARCH_UPSTREAM_ERROR");
    }
    throw err;
  }
}
```

```typescript
// ❌ DON'T — src/services/search.ts com múltiplos problemas
import { SearchClient } from "@azure/search-documents";
import { config } from "../shared/config"; // ❌ sem .js
import { logger } from "../shared/logger"; // ❌ sem .js

export async function searchChunks(embedding: any, requestId: any) { // ❌ any
  const client = new SearchClient(
    process.env.AZURE_SEARCH_ENDPOINT!, // ❌ process.env direto
    process.env.AZURE_SEARCH_INDEX_NAME!,
    { key: process.env.AZURE_SEARCH_API_KEY! }
  );

  return client.search("*", { ... }).then((res) => {   // ❌ .then()
    const chunks = [];
    for await (const r of res.results) chunks.push(r); // ❌ dado não tipado
    return chunks;
  }).catch(() => []); // ❌ engolindo erro, retornando estado indefinido
}
```

### Schema Zod com export correto

```typescript
// ✅ DO — src/schemas/query.ts
import { z } from "zod";

export const InputSchema = z.object({
  question: z.string().min(1).max(500),
});

export const OutputSchema = z.object({
  answer: z.string(),
  sources: z.array(z.string()),
});

export type QueryInput  = z.infer<typeof InputSchema>;
export type QueryOutput = z.infer<typeof OutputSchema>;
```

---

## Anti-padrões

### AP-1: Omitir a extensão `.js` no import

**Problema:** o código compila mas falha em runtime com `ERR_MODULE_NOT_FOUND`.

```typescript
// ❌
import { config } from "../shared/config";
// ✅
import { config } from "../shared/config.js";
```

**Por quê acontece:** TypeScript com `"moduleResolution": "bundler"` aceita sem extensão, mas o Node ESM exige a extensão real no arquivo emitido. O compilador não injeta `.js` automaticamente.

---

### AP-2: Usar `any` para contornar um erro de tipo

**Problema:** silencia o compilador mas abre brechas para acessos inválidos em runtime.

```typescript
// ❌
const body: any = await request.json();
const answer = body.choices[0].message.content; // explode se choices[] estiver vazio
```

**Correção:** use `unknown` + parse Zod, ou type guard explícito.

---

### AP-3: Validar dados externos com `typeof` manual em vez de Zod

**Problema:** validações manuais são incompletas, inconsistentes e não geram tipos automaticamente.

```typescript
// ❌
if (typeof body.question !== "string") return { status: 400 };
// ✅
const result = InputSchema.safeParse(body);
if (!result.success) return { status: 400, jsonBody: { error: result.error.flatten() } };
```

---

### AP-4: Criar `index.ts` de re-export (barrel)

**Problema:** cria dependências implícitas, dificulta tree-shaking e pode criar ciclos de importação.

```typescript
// ❌ src/services/index.ts
export { searchChunks } from "./search.js";
export { getCompletion } from "./completion.js";
```

**Correção:** importe sempre o módulo diretamente.

---

### AP-5: Misturar `.then()/.catch()` com `async/await` no mesmo fluxo

**Problema:** dificulta rastreamento de erros; `await` e `.catch()` tratam erros de formas diferentes.

```typescript
// ❌
const result = await somePromise.catch((err) => null);
if (!result) throw new Error("failed");

// ✅
try {
  const result = await somePromise;
} catch (err) {
  throw new DomainError("...", "ERROR_CODE");
}
```

---

### AP-6: Usar `process.env` diretamente fora de `src/shared/config.ts`

**Problema:** dispersa a configuração, torna testes frágeis e impede validação centralizada.

```typescript
// ❌ src/services/completion.ts
const endpoint = process.env.AZURE_OPENAI_ENDPOINT!;

// ✅
import { config } from "../shared/config.js";
const endpoint = config.AZURE_OPENAI_ENDPOINT;
```

---

## Checklist rápido antes de gerar código

- [ ] Todos os imports têm extensão `.js`
- [ ] Nenhum `any` — use `unknown` + Zod para dados externos
- [ ] Todo dado externo (HTTP body, env var, resposta de IA) passa por `Schema.parse()` ou `Schema.safeParse()`
- [ ] Apenas `async/await` — sem `.then()/.catch()` encadeados
- [ ] Nenhum `catch {}` vazio — propague ou envolva em erro de domínio
- [ ] Nomes seguem a tabela de convenções (PascalCase / camelCase / UPPER_SNAKE_CASE / kebab-case)
- [ ] Nenhum `index.ts` barrel criado
- [ ] Configuração lida exclusivamente via `config` importado de `src/shared/config.ts`
