# Code Review — `response-validator.ts`

**Arquivo:** `src/services/response-validator.ts`  
**Data:** 2026-06-29  
**Status:** Todos os problemas corrigidos

---

## Resumo

| # | Severidade | Problema | Status |
|---|-----------|----------|--------|
| 1 | Crítico | Schema aceita campos extras silenciosamente | Corrigido |
| 2 | Atenção | Guardrail G2 não cobre variações morfológicas | Corrigido |
| 3 | Atenção | Marcador de negação truncado + `SAFE_DEFAULT` mutável | Corrigido |
| 4 | Novo | Ausência de guardrail de idioma (PT-BR) | Adicionado |

---

## Problema 1 — Schema aceita campos extras silenciosamente

**Severidade:** Crítico  
**Localização:** `StructuredResponseSchema`, linha 4

### Descrição

O Zod usa o modo `.strip()` por padrão: chaves desconhecidas são silenciosamente descartadas e `safeParse` retorna `success: true`. Se o LLM retornar campos inesperados (ex: `_debug`, `inject`, `metadata`), o comportamento passa despercebido pelo sistema de validação.

### Correção

```diff
- }).;
+ }).strict();
```

Com `.strict()`, qualquer chave fora do schema faz a validação falhar, derrubando para o `SAFE_DEFAULT` e gerando o log de aviso correspondente.

---

## Problema 2 — Guardrail G2 cobre variações muito estreitas

**Severidade:** Atenção  
**Localização:** `passesDangerousCargoGuardrail`, linhas 37–39

### Descrição

As buscas literais por `includes` não cobrem variações morfológicas comuns:

- `"carga perigosa"` não captura **"cargas perigosas"** (plural)
- `"devolução"` / `"devolucao"` não captura as formas verbais **"devolver"**, **"devolvendo"**, **"devolvido"**

Uma resposta do modelo que use essas variações passa pelo guardrail sem ser interceptada.

### Correção

Substituição por expressões regulares com cobertura morfológica:

```diff
- const hasDangerousCargo = lower.includes("carga perigosa");
- const hasReturn =
-   lower.includes("devolução") || lower.includes("devolucao");
+ const hasDangerousCargo =
+   /cargas?\s+perigosas?|material\s+perigoso|produto\s+perigoso/.test(lower);
+ const hasReturn =
+   /devolu[cç][aã]o|devolver(do|ndo)?|retorno\s+de\s+carga/.test(lower);
```

---

## Problema 3 — Marcador de negação truncado e `SAFE_DEFAULT` mutável

**Severidade:** Atenção  
**Localização:** `negationMarkers` linha 54; `validateResponse` linhas 72, 88, 101

### 3a — Marcador truncado

O marcador `"não é permitid"` estava incompleto: como o `includes` busca a substring literal, a string `"não é permitido"` passa pelo teste apenas pela presença de `"não"` (outro item da lista), não pelo marcador intencionado.

```diff
- "não é permitid",
+ "não é permitido",
+ "não é permitida",
```

### 3b — `SAFE_DEFAULT` retornado por referência

`validateResponse` retornava a referência direta ao objeto `SAFE_DEFAULT`. Se o chamador mutasse o resultado (ex: `result.answer = "outro texto"`), o singleton interno seria modificado e todas as chamadas seguintes retornariam o default corrompido.

```diff
- return SAFE_DEFAULT;
+ return { ...SAFE_DEFAULT };
```

A correção foi aplicada nos 3 pontos de retorno da função.

---

## Adição — Guardrail G3: idioma português obrigatório

**Localização:** nova função `passesPortugueseLanguageGuardrail`

### Motivação

Toda a documentação de origem (`docs/novatech/`) está em PT-BR. Respostas em inglês indicam que o modelo ignorou o contexto dos documentos ou foi induzido a responder em outro idioma.

### Implementação

A detecção usa dois sinais complementares sem dependências externas:

1. **Caracteres exclusivos do português** — `ã` e `õ` não ocorrem em inglês nem espanhol com a mesma frequência
2. **Palavras funcionais de alta frequência** — `não`, `está`, `são`, `também`, `então`, `assim`, `pelo`, `pela`, `isso`, `esse`, `essa`, `seria`, `foram`, `precisa` — delimitadas por `\b` para evitar falsos positivos dentro de outras palavras

```typescript
function passesPortugueseLanguageGuardrail(answer: string): boolean {
  if (/[ãõÃÕ]/.test(answer)) return true;

  return /\b(não|está|são|também|então|assim|pelo|pela|isso|esse|essa|seria|foram|precisa)\b/i.test(
    answer,
  );
}
```

Se nenhum dos dois sinais estiver presente, a resposta é bloqueada com log `G3_portuguese_language_required` e retorna o `SAFE_DEFAULT`.

### Limitação conhecida

Respostas muito curtas sem acentuação e sem as palavras da lista podem gerar falsos negativos. Em produção, considerar complementar com detecção probabilística de idioma (ex: biblioteca `franc`) se o volume de falsos bloqueios se mostrar significativo.
