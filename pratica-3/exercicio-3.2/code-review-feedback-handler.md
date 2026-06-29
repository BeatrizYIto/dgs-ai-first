# Code Review — `src/functions/feedback/handler.ts`

**Revisor:** GitHub Copilot
**Data:** 2026-06-29
**Arquivo analisado:** `src/functions/feedback/handler.ts`

---

## Resumo

O arquivo apresenta **4 violações diretas** das regras de desenvolvimento definidas para o projeto. Nenhuma delas é opcional — todas bloqueiam aprovação do PR.

---

## Problemas Encontrados

### 🔴 [BLOQUEANTE] `require` dinâmico dentro da função

**Regra violada:** _"Imports estáticos no topo (nunca `require` dinâmico)."_

```ts
// ❌ Atual
const { CosmosClient } = require("@azure/cosmos");
```

`require` dinâmico dentro do corpo da função impede tree-shaking, dificulta análise estática e viola a regra explícita do projeto. Com `"type": "module"` no `package.json`, isso também pode causar erros em runtime dependendo do bundler.

**Correção:**

```ts
// ✅ Correto — importar no topo do arquivo
import { CosmosClient } from "@azure/cosmos";
```

---

### 🔴 [BLOQUEANTE] Uso de `console.log` em vez de `pino`

**Regra violada:** _"pino para logging (nunca `console.log`)."_

```ts
// ❌ Atual
console.log("Feedback recebido:", JSON.stringify(feedback));
```

`console.log` não oferece níveis de log estruturados, não é configurável por ambiente e não integra com pipelines de observabilidade.

**Correção:**

```ts
// ✅ Correto
import { logger } from "../../shared/logger";

logger.info(
  { queryId: feedback.queryId, rating: feedback.rating },
  "Feedback recebido",
);
```

---

### 🔴 [BLOQUEANTE] Dado pessoal logado sem mascaramento

**Regra violada:** _"Nunca logar dados pessoais (e-mail, nome)."_

```ts
// ❌ Atual — loga o objeto feedback completo, que contém attendantEmail
console.log("Feedback recebido:", JSON.stringify(feedback));
```

O campo `attendantEmail` é um dado pessoal (PII). Logá-lo integralmente viola a regra de privacidade e pode gerar não-conformidade com LGPD.

**Correção:**
Logar apenas os campos não-sensíveis, como demonstrado no item anterior (`queryId`, `rating`). Nunca serializar o objeto completo quando ele contém PII.

---

### 🔴 [BLOQUEANTE] Ausência de validação de input com Zod

**Regra violada:** _"Zod para validação de input."_

```ts
// ❌ Atual — cast para any sem nenhuma validação
const body = (await request.json()) as any;

const feedback = {
  queryId: body.queryId,   // pode ser undefined, null, número, objeto...
  rating: body.rating,
  ...
};
```

O input do usuário é aceito sem nenhuma validação de tipos, formatos ou presença de campos obrigatórios. Isso abre espaço para dados corrompidos no banco e potenciais vulnerabilidades (injeção de campos inesperados).

**Correção:**

```ts
// ✅ Correto — definir schema Zod e validar antes de usar
import { z } from "zod";

const FeedbackSchema = z.object({
  queryId: z.string().uuid(),
  rating: z.number().int().min(1).max(5),
  comment: z.string().max(1000).optional(),
  attendantEmail: z.string().email(),
});

const parsed = FeedbackSchema.safeParse(await request.json());
if (!parsed.success) {
  return { status: 400, body: JSON.stringify(parsed.error.flatten()) };
}
const feedback = { ...parsed.data, timestamp: new Date().toISOString() };
```

---

### ⚠️ [ATENÇÃO] `zod` em `devDependencies`

**Arquivo:** `package.json`

`zod` está listado apenas em `devDependencies`, mas é necessário em runtime para validação de inputs. Deve ser movido para `dependencies`.

```json
// ❌ Atual
"devDependencies": {
  "zod": "^3.23.0"
}

// ✅ Correto
"dependencies": {
  "zod": "^3.23.0"
}
```

---

## Resumo das Violações

| #   | Severidade    | Regra Violada                             | Linha(s)     |
| --- | ------------- | ----------------------------------------- | ------------ |
| 1   | 🔴 Bloqueante | `require` dinâmico dentro da função       | 17           |
| 2   | 🔴 Bloqueante | `console.log` em vez de `pino`            | 16           |
| 3   | 🔴 Bloqueante | PII (`attendantEmail`) logado sem máscara | 16           |
| 4   | 🔴 Bloqueante | Ausência de validação Zod no input        | 6–14         |
| 5   | ⚠️ Atenção    | `zod` em `devDependencies`                | package.json |

---

## Ação Requerida

PR **não aprovado**. Todos os itens 🔴 devem ser corrigidos antes de novo review.
