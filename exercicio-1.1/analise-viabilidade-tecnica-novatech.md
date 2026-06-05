# Análise de Viabilidade Técnica — Assistente de IA NovaTech
**Projeto:** Assistente Conversacional para Atendimento ao Cliente
**Cliente:** NovaTech | **Fornecedor:** DB1 | **Versão:** 0.2 (revisão crítica adicionada)
**Data:** 2026-06-05

---

## 1. Sumário Executivo

Este documento analisa a viabilidade técnica de construir um **assistente de IA conversacional baseado em RAG (Retrieval-Augmented Generation)** para o time de atendimento da NovaTech, com foco em:

- Arquitetura recomendada dado o stack Microsoft 365 já adotado
- Viabilidade de indexação das três fontes documentais existentes
- **Impacto do gerenciamento de contexto na arquitetura** — como a janela de contexto dos modelos de linguagem afeta as decisões de design
- Riscos técnicos e mitigações

**Veredito geral:** viável com ressalvas — as principais variáveis de risco são a qualidade da documentação existente (contradições entre versões) e a estratégia de chunking para documentos longos.

---

## 2. Arquitetura Proposta — Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                        Microsoft Teams                          │
│                    (interface do atendente)                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ pergunta em linguagem natural
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Bot Framework / Azure Bot Service            │
│             (orquestrador da conversa + histórico)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌─────────────────────┐     ┌───────────────────────┐
│  Azure AI Search    │     │   Azure OpenAI         │
│  (índice vetorial)  │     │   (LLM — geração)      │
│                     │     │                        │
│  Chunks dos docs    │────▶│  Prompt = contexto     │
│  SharePoint + Wiki  │     │  recuperado + pergunta │
│  + planilhas        │     │  + histórico recente   │
└─────────────────────┘     └───────────────────────┘
              ▲
              │ indexação / atualização
┌─────────────┴──────────────────────────────────┐
│              Fontes Documentais                 │
│  SharePoint (PDFs/Word) │ Confluence │ Rede     │
└─────────────────────────────────────────────────┘
```

### Componentes principais

| Componente | Serviço Azure | Responsabilidade |
|---|---|---|
| Interface | Microsoft Teams | Canal de comunicação com os 45 atendentes |
| Orquestração | Azure Bot Service + Bot Framework SDK | Gerenciar turnos de conversa, histórico, roteamento |
| Busca semântica | Azure AI Search (vetorial + híbrido) | Recuperar os chunks de documentos mais relevantes |
| Geração de resposta | Azure OpenAI (GPT-4o ou GPT-4.1) | Gerar resposta baseada nos chunks recuperados |
| Embeddings | Azure OpenAI (text-embedding-3-large) | Vetorizar documentos e queries no momento da busca |
| Ingestão contínua | Azure Functions + Logic Apps | Detectar alterações nas fontes e re-indexar |
| Armazenamento | Azure Blob Storage | Armazenar versões dos documentos originais |

---

## 3. Análise por Fonte Documental

### 3.1 SharePoint (PDFs e Word) — Alta viabilidade

- **Conector nativo:** Azure AI Search possui indexador nativo para SharePoint Online
- **Formato:** PDFs e .docx são bem suportados pelo Document Intelligence (OCR, extração estruturada)
- **Risco:** PDFs escaneados (sem camada de texto) exigem OCR — avaliar percentual durante discovery
- **Atualização:** indexador pode ser agendado (ex.: diário) ou acionado via webhook

### 3.2 Confluence (Wiki interna) — Viabilidade média

- **Conector:** não há conector nativo Azure AI Search para Confluence
- **Abordagem:** Confluence REST API → extração periódica via Azure Function → ingestão no índice
- **Formato:** conteúdo HTML/Markdown — requer limpeza antes do chunking
- **Risco:** autenticação e rate limits da API Confluence; páginas com estrutura muito livre podem gerar chunks sem semântica clara

### 3.3 Pasta de rede compartilhada (planilhas) — Viabilidade média-baixa

- **Formato crítico:** planilhas Excel/CSV são o formato mais desafiador para RAG
- **Problema:** células sem contexto ("120", "Cliente Premium") perdem significado fora da tabela
- **Abordagem recomendada:** serializar tabelas em linguagem natural antes do chunking ("Para clientes do tipo Premium, o SLA de entrega é de 2 dias úteis para a região Sudeste")
- **Atualização mensal:** processo de re-ingestão deve ser automatizado via Azure Function com trigger no SharePoint/OneDrive se a pasta for mapeada

---

## 4. Análise por Tipo de Formato — Desafios, Impactos e Estratégias de Tratamento

Esta seção aprofunda os desafios técnicos específicos de cada formato documental presente no ambiente da NovaTech, analisando o impacto de cada um na qualidade das respostas do assistente e definindo uma estratégia de tratamento para o pipeline de ingestão.

---

### 4.1 PDFs com tabelas

#### Desafio para o pipeline RAG

Tabelas em PDFs existem em estrutura **2D (linhas × colunas)**. A extração de texto convencional lê o documento de forma linear, da esquerda para a direita e de cima para baixo, destruindo o relacionamento entre células. Uma tabela de SLA com cabeçalho "Tipo de Cliente | Região | Prazo | Multa por Atraso" vira uma sequência plana como:

```
Padrão Sudeste 3 dias úteis 1,5% Premium Sudeste 1 dia útil 3% Padrão Norte 5 dias úteis ...
```

Ao ser dividida em chunks, essa sequência produz fragmentos sem cabeçalho, completamente sem contexto.

#### Impacto na qualidade das respostas

- O chunk "Premium Sudeste 1 dia útil 3%" é indexado com embedding que não captura o significado de "prazo de SLA"
- A busca semântica pode não recuperar esse chunk para a pergunta "Qual o prazo para cliente Premium no Sudeste?"
- Mesmo que o chunk seja recuperado, o modelo não consegue estruturar uma resposta clara a partir de dados soltos

#### Estratégia de tratamento

```
PDF → Azure Document Intelligence (modelo de layout)
     ↓
Extração estruturada de tabelas (API retorna objeto Table com rows/cells)
     ↓
Serialização linha a linha em linguagem natural:
"Para clientes do tipo Premium na região Sudeste,
 o prazo de entrega é de 1 dia útil e a multa
 por atraso é de 3% sobre o valor da nota."
     ↓
Chunk por linha serializada (+ metadados: nome do doc, seção, data)
     ↓
Ingestão no índice
```

**Critério de aceite:** cada chunk deve ser compreensível isoladamente, sem depender de linhas adjacentes para ter significado.

---

### 4.2 PDFs escaneados (sem camada de texto)

#### Desafio para o pipeline RAG

PDFs escaneados são essencialmente **imagens embutidas em um container PDF**. A extração de texto convencional retorna string vazia ou, no pior caso, artefatos ininteligíveis. Sem texto, não há o que vetorizar — o documento existe no repositório mas é invisível para o sistema RAG.

Na NovaTech, esse risco é real para manuais operacionais antigos que podem ter sido digitalizados sem OCR.

#### Impacto na qualidade das respostas

- O chunk indexado está vazio ou tem lixo: o embedding gerado não representa o conteúdo real
- A busca semântica nunca recupera esses documentos, mesmo que sejam a fonte mais autoritativa para uma pergunta
- O modelo responde "não encontrei informações sobre isso" — falso negativo que erode a confiança do atendente no sistema

#### Estratégia de tratamento

```
PDF detectado sem camada de texto (heurística: <50 tokens por página)
     ↓
Azure AI Document Intelligence — Read API (OCR de alta precisão)
     ↓
Pós-processamento de erros OCR comuns em português:
  - normalizar ã/â/á, ç, ê, ô, õ
  - remover artefatos de digitalização (linhas, headers repetidos)
     ↓
Validação de qualidade:
  - se >30% dos tokens do chunk forem inválidos (sequências sem vogal, etc.)
  → marcar chunk com flag "baixa_confianca" e acionar revisão humana
     ↓
Ingestão normal com metadado "origem: ocr" para rastreabilidade
```

**Ação de discovery obrigatória:** antes do desenvolvimento, amostrar 50 documentos do SharePoint e medir o percentual de PDFs escaneados — esse número define o esforço e custo do pipeline de OCR.

---

### 4.3 Wiki com links internos (Confluence)

#### Desafio para o pipeline RAG

Páginas Confluence têm estrutura **altamente hiperligada e com muito ruído estrutural**:

- Links internos: `[Veja também: Política de Devolução](https://confluence.novatech/...)` — aparecem no texto mas não trazem conteúdo
- Macros Atlassian: `{panel}`, `{info}`, `{warning}` — geram texto de template sem semântica útil
- Tabelas de conteúdo automáticas, breadcrumbs de navegação, rodapés com metadados de edição
- Páginas que são apenas sumários com links — conteúdo real está nas subpáginas

#### Impacto na qualidade das respostas

- Chunks cheios de tags e URLs diluem o conteúdo semântico útil — o embedding representa "ruído + informação" em vez de "informação"
- Links internos mencionados no chunk mas não resolvidos criam referências vazias: o modelo cita "consulte a Política X" mas não tem acesso ao conteúdo de X
- Fragmentação das informações entre página-pai e subpáginas pode impedir que uma resposta completa seja montada

#### Estratégia de tratamento

```
Confluence REST API → export de página em formato "storage" (XML/HTML)
     ↓
Limpeza em camadas:
  1. Remover macros Atlassian e tags de navegação
  2. Remover links de "Veja também" e breadcrumbs
  3. Preservar estrutura semântica: títulos H1/H2/H3 → metadados do chunk
     (não como texto dentro do chunk, mas como campo "secao" no índice)
     ↓
Resolução parcial de links:
  - Para links para páginas no mesmo espaço Confluence:
    verificar se a página linkada já está no índice
    se não: adicionar à fila de ingestão
     ↓
Chunking por seção (split em H2/H3) em vez de por tamanho fixo de tokens
  — respeita fronteiras semânticas naturais do documento
     ↓
Ingestão com metadados: page_id, space, título, seção, data_modificacao
```

**Vantagem do chunking por seção:** perguntas sobre um tema específico recuperam chunks inteiros de seções coerentes, não fragmentos arbitrários cortados no meio de um parágrafo.

---

### 4.4 Planilhas com fórmulas (Excel/CSV)

#### Desafio para o pipeline RAG

Planilhas têm dois problemas sobrepostos:

1. **Fórmulas:** `=SE(B2="Premium";1;SE(B2="Padrão";3;5))` não tem significado semântico — é código, não linguagem natural. O embedding de uma célula com fórmula representa a sintaxe da função, não o valor calculado.

2. **Dependências entre células:** o valor de uma célula pode depender de outra em uma aba diferente. Extrair células isoladamente quebra o contexto que dá significado aos dados.

No contexto da NovaTech, as planilhas contêm tabelas de SLA, regras de cálculo de frete e políticas comerciais — exatamente o tipo de informação mais consultada pelos atendentes.

#### Impacto na qualidade das respostas

- Fórmulas indexadas como string resultam em chunks que nunca são recuperados por buscas em linguagem natural
- Valores numéricos sem unidade e sem contexto ("120", "0.015") são ininterpretáveis
- A resposta gerada pode conter o valor correto mas sem a explicação de quando e como ele se aplica

#### Estratégia de tratamento

```
Planilha Excel recebida (atualização mensal)
     ↓
Etapa 1 — Avaliação de fórmulas:
  Abrir com openpyxl (data_only=True) ou equivalente
  → substituir fórmulas pelo valor calculado atual
     ↓
Etapa 2 — Serialização contextualizada:
  Para cada linha da tabela de dados:
    combinar cabeçalho de coluna + valor da célula em sentença:
    "Tipo de cliente: Premium | Região: Sudeste | Prazo SLA: 1 dia útil
     | Multa por atraso: 3% | Janela de atendimento: 8h–18h"
    → converter para prosa:
    "Para clientes Premium na região Sudeste, o SLA garante entrega
     em até 1 dia útil. Atrasos geram multa de 3%. O atendimento
     ocorre das 8h às 18h."
     ↓
Etapa 3 — Ingestão com metadados de versão:
  Incluir: nome_arquivo, aba, data_extracao, hash_conteudo
  (hash permite detectar mudanças e re-indexar apenas o que mudou)
     ↓
Etapa 4 — Re-ingestão mensal automatizada:
  Azure Function com trigger agendado (1º dia útil de cada mês)
  → comparar hash atual com o hash anterior
  → re-indexar somente as linhas alteradas
```

**Ponto crítico de governança:** planilhas com fórmulas que referenciam dados externos (outras abas, outros arquivos) devem ser avaliadas manualmente antes da ingestão para garantir que os valores calculados estão corretos no momento da extração.

---

### 4.5 Resumo comparativo — Esforço e risco por tipo de formato

| Tipo | Dificuldade de ingestão | Risco para qualidade RAG | Esforço de tratamento |
|---|---|---|---|
| PDF digital com texto corrido | Baixa | Baixo | Baixo — indexador nativo |
| PDF digital com tabelas | Média | Alto sem tratamento | Médio — serialização necessária |
| PDF escaneado (sem texto) | Alta | Crítico sem OCR | Alto — OCR + pós-processamento |
| Wiki Confluence (texto estruturado) | Média | Médio | Médio — limpeza + chunking semântico |
| Planilha com dados simples | Média | Alto sem serialização | Médio — serialização linha a linha |
| Planilha com fórmulas complexas | Alta | Crítico sem avaliação | Alto — avaliação + serialização + revisão |

---

## 5. Estimativa do Tamanho da Base em Tokens

Esta seção dimensiona o volume total da base documental da NovaTech em tokens — unidade de medida relevante para decisões de arquitetura como capacidade do índice, custo de ingestão e número de chunks gerados.

### 5.1 Premissas do cálculo

| Premissa | Valor |
|---|---|
| Regra prática de conversão | 1 token ≈ 0,75 palavras → **tokens = palavras ÷ 0,75** |
| Palavras por página de PDF (média documentos corporativos) | ~250 palavras/página |
| Chunk size adotado | 600 tokens |
| Overlap entre chunks | 100 tokens → passo efetivo de 500 tokens |
| Planilhas: após serialização, palavras por linha | ~30 palavras/linha |
| Planilhas: linhas por planilha (estimativa) | ~200 linhas |

> A regra 1 token ≈ 0,75 palavras é o padrão OpenAI para textos em inglês. Para português, que tem palavras ligeiramente mais longas em média, o resultado pode ser ~5–10% maior. Os cálculos abaixo usam a regra padrão como base conservadora.

---

### 5.2 Estimativa por fonte

#### PDFs e documentos Word — SharePoint

```
800 documentos × 10 páginas/doc × 250 palavras/página
= 2.000.000 palavras brutas

Tokens = 2.000.000 ÷ 0,75 = 2.666.667 tokens ≈ 2,7M tokens
```

#### Páginas Wiki — Confluence

```
400 páginas × 1.500 palavras/página
= 600.000 palavras brutas

Tokens = 600.000 ÷ 0,75 = 800.000 tokens ≈ 800K tokens
```

#### Planilhas de referência — pasta de rede

Planilhas não são contadas em "palavras por página". Após a **serialização em linguagem natural** (ver seção 4.4), cada linha da tabela vira uma sentença:

```
50 planilhas × 200 linhas/planilha × 30 palavras/linha serializada
= 300.000 palavras

Tokens = 300.000 ÷ 0,75 = 400.000 tokens ≈ 400K tokens
```

> Nota: planilhas antes da serialização têm volume muito menor (células são curtas). O volume acima representa o texto **após expansão em linguagem natural** — que é o que efetivamente entra no índice.

---

### 5.3 Consolidação — total bruto

| Fonte | Palavras | Tokens (bruto) | % do total |
|---|---|---|---|
| SharePoint (PDFs + Word) | 2.000.000 | **2.700.000** | 69% |
| Confluence (wiki) | 600.000 | **800.000** | 20% |
| Planilhas (pós-serialização) | 300.000 | **400.000** | 10% |
| **Total** | **2.900.000** | **~3.900.000** | 100% |

**Base total estimada: ~3,9 milhões de tokens.**

---

### 5.4 Número estimado de chunks gerados

Com chunk size = 600 tokens e overlap = 100 tokens (passo efetivo = 500 tokens):

```
chunks por fonte = tokens da fonte ÷ 500 (passo efetivo)

PDFs:       2.700.000 ÷ 500 = ~5.400 chunks
Confluence:   800.000 ÷ 500 = ~1.600 chunks
Planilhas:    400.000 ÷ 500 =   ~800 chunks
                               ─────────────
Total:                         ~7.800 chunks
```

> O chunking por seção semântica (H2/H3) usado no Confluence pode reduzir esse número, pois seções completas menores que 600 tokens geram um único chunk — não são forçadas ao tamanho máximo.

---

### 5.5 Implicações arquiteturais

#### Capacidade do índice vetorial

```
7.800 chunks × 3.072 dimensões (text-embedding-3-large) × 4 bytes/float
≈ 96 MB de dados vetoriais
```

O Azure AI Search **Basic tier** suporta até **2 GB** de storage — a base vetorial de 96 MB da NovaTech cabe com folga. O Standard S1 (25 GB/partição) seria necessário apenas se a base crescer 20×. O dimensionamento de tier pode ser guiado pelo custo, não pela capacidade.

> ⚠️ **Nota de correção (v0.2):** versões anteriores deste documento indicavam incorretamente "15 GB" para o Basic tier. O valor correto é 2 GB.

#### Custo de ingestão (embeddings) — único

```
3,9M tokens × $0,13 / 1M tokens (text-embedding-3-large)
≈ U$ 0,51 — custo único de indexação inicial
```

#### Re-ingestão mensal (planilhas + documentos alterados)

Assumindo ~20% de churn mensal nos documentos:

```
Planilhas (re-ingestão total):   400K tokens
Docs alterados (20% dos PDFs):   540K tokens
Wiki (alterações pontuais):      ~80K tokens
─────────────────────────────────────────────
Total mensal re-indexado:        ~1,0M tokens → ≈ U$ 0,13/mês
```

#### Relação entre base e top_k

Com ~7.800 chunks no índice e `top_k = 5` por consulta:

```
5 chunks recuperados ÷ 7.800 total = 0,06% da base por consulta
```

Isso confirma que a **qualidade da busca semântica é crítica** — o sistema precisa encontrar os 5 chunks corretos entre 7.800 candidatos. Um erro de precisão nessa etapa não é recuperável na etapa de geração.

---

### 5.6 Referência visual — distribuição da base

```
Tokens na base (~3,9M total)

PDFs (SharePoint)   ████████████████████████████░░░░░  2,7M  (69%)
Wiki (Confluence)   ████████░░░░░░░░░░░░░░░░░░░░░░░░░    800K  (21%)
Planilhas           ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    400K  (10%)
```

---

## 6. Gerenciamento de Contexto — Impacto na Arquitetura

Esta seção analisa como as **limitações e características da janela de contexto dos modelos de linguagem** afetam diretamente as decisões de arquitetura do sistema RAG.

### 6.1 O que é a janela de contexto e por que ela importa aqui

Um modelo como o GPT-4o recebe, em cada chamada de API, um **bloco único de texto** (o prompt) que inclui:

```
[instrução do sistema]
+ [chunks recuperados do índice]
+ [histórico recente da conversa]
+ [pergunta atual do atendente]
= TOTAL (limitado pela janela de contexto)
```

Para o GPT-4o, a janela é de **128.000 tokens** (~96.000 palavras). Parece amplo, mas o custo por token e a latência crescem com o tamanho — e mais contexto nem sempre melhora a resposta (fenômeno "lost in the middle").

### 6.2 Decisão crítica: tamanho e estratégia de chunking

O chunking é a divisão dos documentos em fragmentos indexáveis. Essa decisão tem impacto direto na qualidade das respostas:

| Estratégia | Chunk size | Prós | Contras |
|---|---|---|---|
| Chunks pequenos | ~200–400 tokens | Alta precisão na busca semântica | Perda de contexto local; resposta pode ser incompleta |
| Chunks médios | ~500–800 tokens | Equilíbrio | Recomendado como ponto de partida |
| Chunks grandes | ~1.000–1.500 tokens | Mais contexto por fragmento | Menor precisão na busca; mais tokens consumidos por chunk |
| HyDE / Proposicional | variável | Alta precisão | Maior complexidade de implementação |

**Recomendação inicial:** chunks de 600 tokens com overlap de 100 tokens, revisados após avaliação qualitativa nas primeiras iterações.

### 6.3 Quantos chunks incluir no prompt?

Definir o número de chunks (`top_k`) a recuperar e injetar no prompt é uma trade-off direta entre custo/latência e qualidade:

| top_k | Tokens médios no prompt | Impacto |
|---|---|---|
| 3 | ~1.800 tokens | Rápido, barato — risco de não cobrir a resposta |
| 5 | ~3.000 tokens | Ponto de partida razoável |
| 10 | ~6.000 tokens | Melhor cobertura — avaliar se o modelo usa todos |
| 20+ | ~12.000+ tokens | Latência e custo elevados sem ganho proporcional |

**Decisão arquitetural:** começar com `top_k = 5`, com re-ranker (Azure AI Search semantic ranking) para garantir que os 5 chunks sejam os mais relevantes, não apenas os mais similares em vetor.

### 6.4 Histórico de conversa — gerenciamento explícito obrigatório

Atendentes usam o assistente ao longo de chamados. A conversa **não pode ser infinita** no contexto:

```
Turno 1: "Qual o prazo para devolução de produto avariado?"
Turno 2: "E se o cliente estiver no interior do Paraná?"
Turno 3: "Qual o procedimento para acionar o seguro nesse caso?"
```

No turno 3, o modelo precisa de contexto dos turnos anteriores para entender "nesse caso". Estratégias:

| Estratégia | Descrição | Adequação para NovaTech |
|---|---|---|
| Janela deslizante | Mantém os N turnos mais recentes | Simples — adequado para chamados curtos |
| Resumo automático | Sumariza turnos antigos em vez de descartá-los | Adequado se chamados forem longos |
| Buffer por entidade | Extrai entidades-chave (cliente, produto, região) e as mantém | Alta qualidade, maior complexidade |

**Recomendação:** janela deslizante com os últimos **6 turnos** (3 do atendente + 3 do assistente), suficiente para o fluxo típico de um chamado de atendimento.

### 6.5 Problema das contradições documentais — implicação para o contexto

O contexto menciona que há **versões contraditórias de documentos**. Quando dois chunks contraditórios são recuperados simultaneamente e injetados no prompt, o modelo pode:

- Escolher arbitrariamente um dos dois
- Apresentar ambas as versões sem indicar qual é a correta
- Alucinar uma síntese incorreta

**Mitigação arquitetural necessária:**
1. Incluir metadados de data/versão em cada chunk
2. Adicionar instrução no system prompt: "Se houver informações contraditórias entre os documentos recuperados, apresente as duas versões, indique as fontes e oriente o atendente a consultar o responsável pela área"
3. Implementar processo de governança de conteúdo (fora do escopo técnico, mas bloqueante para qualidade)

---

### 6.6 Orçamento de contexto por query — análise de capacidade

#### Decomposição da janela de 128K tokens

O GPT-4o disponibiliza 128.000 tokens por chamada. Esse espaço é compartilhado por todos os componentes do prompt:

```
┌──────────────────────────────────────────────────────────────┐
│              JANELA DE CONTEXTO — 128.000 tokens             │
├──────────────────────────────────────────────────────────────┤
│  System prompt + instruções de comportamento    ~2.000 tok   │
│  Histórico de conversa (últimos 6 turnos)         ~600 tok   │
│  Pergunta do atendente (turno atual)               ~50 tok   │
│  Reserva para geração da resposta          ~800–1.500 tok   │
│  ─────────────────────────────────────────────────────────   │
│  Subtotal fixo por query:               ~3.450–4.150 tok    │
│                                                              │
│  Disponível para chunks recuperados:  ~123.850–124.550 tok  │
└──────────────────────────────────────────────────────────────┘
```

#### Quantos chunks cabem?

Com chunks de **500 tokens** (chunk size 600 − overlap 100):

```
124.850 ÷ 500 = ~249 chunks — capacidade máxima teórica
```

Porém, usar 249 chunks é contraproducente. O fenômeno **"lost in the middle"** (Shi et al., 2023) demonstra que modelos de linguagem tendem a ignorar informações posicionadas no meio de contextos muito longos, privilegiando o início e o fim do prompt.

#### Trade-off real: top_k × qualidade × custo

| top_k | Tokens (chunks) | Total no prompt | Custo input\* | Risco "lost in middle" |
|---|---|---|---|---|
| 3 | 1.500 | ~4.650 | baixíssimo | Nenhum — mas cobertura limitada |
| **5** | **2.500** | **~5.650** | **~U$0,014/query** | **Desprezível — ponto de partida** |
| 10 | 5.000 | ~8.150 | ~U$0,020/query | Baixo — aceitável com re-ranker |
| 20 | 10.000 | ~13.150 | ~U$0,033/query | Moderado — chunks do meio podem ser ignorados |
| 50 | 25.000 | ~28.150 | ~U$0,070/query | Alto — degradação perceptível |
| 249 | 124.500 | ~127.650 | ~U$0,319/query | Crítico — inviável na prática |

\* GPT-4o: U$2,50/1M tokens de input + U$10,00/1M tokens de output (~400 tokens de saída)

#### Implicação direta na estratégia de chunking

O orçamento disponível (~124K tokens) é amplo o suficiente para nunca ser o fator limitante — o limitante real é a **qualidade da atenção do modelo**, não o espaço físico. Isso implica três decisões arquiteturais concretas:

**1. Chunks menores são preferíveis, mas têm um piso de semântica**

```
Muito pequeno  (< 200 tokens): Alta precisão na busca,
               mas chunk pode ser incompleto para responder

Ideal          (400–600 tokens): Balanço entre precisão de busca
               e riqueza semântica suficiente para gerar resposta

Muito grande   (> 1.000 tokens): Chunk cobre mais conteúdo,
               mas busca semântica perde precisão — o vetor
               representa um "média" de múltiplos tópicos
```

**2. top_k = 5 com re-ranker supera top_k = 20 sem re-ranker**

Recuperar 5 chunks altamente relevantes é melhor do que recuperar 20 e colocar os menos relevantes no meio do prompt. A ordem no prompt importa: colocar os chunks mais relevantes no início e no final do bloco de contexto melhora a atenção do modelo.

**3. Para os dados da NovaTech especificamente**

As linhas serializadas de planilhas (~50 tokens cada) são muito menores que o chunk ideal. A estratégia correta é **agrupar linhas relacionadas** no mesmo chunk:

```python
# Exemplo: tabela de SLA serializada em chunks coerentes
chunk_1 = """
Clientes do segmento Premium na região Sudeste:
- SLA de entrega: 1 dia útil
- Multa por atraso: 3% sobre o valor da nota
- Janela de atendimento: 8h–18h (dias úteis)
- Protocolo de escalação: direto para supervisor em < 2h
"""  # ~50 tokens — agrupar com outros clientes da mesma região
```

Isso gera chunks de ~400–500 tokens com contexto completo, sem o fragmento de 50 tokens que perderia a relação entre colunas.

#### Recomendação final para NovaTech

```
top_k = 5 a 8, com Azure AI Search semantic reranker
Chunk size = 500–600 tokens (400 para planilhas agrupadas)
Posicionamento no prompt: chunks mais relevantes primeiro e último,
menos relevantes no meio — mitigação do "lost in the middle"
```

---

### 6.7 Estratégia de chunking recomendada — justificativa por tipo de pergunta e "lost in the middle"

#### Perfil das perguntas que os atendentes farão

O contexto da NovaTech deixa claro quais tipos de consulta dominam os ~192 chamados/dia com busca documental. Cada tipo impõe requisitos distintos ao chunking:

| Tipo de pergunta | Exemplo real | O que o chunk precisa conter |
|---|---|---|
| **Factual de lookup** | "Qual o SLA para cliente Premium no Sudeste?" | O fato específico + unidade + condição |
| **Procedural** | "Quais os passos para abrir reclamação de atraso?" | O procedimento **completo** — não fragmentado entre chunks |
| **Condicional / política** | "Em quais casos o cliente pode recusar a entrega?" | Regra + condições + exceções juntas — nunca separadas |
| **Comparativa entre cenários** | "E se o cliente for da região Norte?" | Todos os dados relevantes da mesma categoria lógica |

A consequência direta: **um único tamanho de chunk aplicado uniformemente a todos os documentos compromete pelo menos dois desses tipos de pergunta**.

---

#### O fenômeno "lost in the middle" e sua implicação prática

Pesquisas sobre atenção de LLMs em contextos longos mostram que o modelo tende a focar no **início e no final** do bloco de contexto, subutilizando o que está no meio:

```
Atenção do modelo ao longo dos chunks no prompt

Alta   ▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░▓▓▓▓
       ↑                              ↑
     chunk 1                       chunk N
     (início)                        (fim)

Baixa       chunk 2   chunk 3  ...  chunk N-1
                 (zona de baixa atenção)
```

Para a NovaTech, com `top_k = 5 a 8`, o efeito é manejável. Mas ele impõe **duas decisões obrigatórias**:

1. **Não usar top_k alto sem re-ranker** — com 20+ chunks, os do meio (posições 4–17) carregam informação que o modelo vai ignorar, inflando custo sem ganho de qualidade.
2. **Ordenar os chunks no prompt por relevância decrescente** e, se possível, repetir o chunk mais relevante no final — isso maximiza a atenção nas informações críticas.

---

#### Estratégia diferenciada por tipo de documento

##### Tabelas de SLA e frete (perguntas de lookup + comparação)

**Problema do chunking uniforme:**
Cada linha serializada tem ~50 tokens. Com chunk de 500 tokens, um único chunk agrupa ~10 linhas. Se as 10 linhas misturarem regiões diferentes (Sudeste, Sul, Norte), a busca vetorial por "Sudeste" recupera um chunk que contém 9 linhas irrelevantes junto com 1 relevante.

**Estratégia correta — agrupamento por categoria lógica:**
```
Chunk A: todas as linhas de clientes Premium (todas as regiões)
Chunk B: todas as linhas de clientes Padrão (todas as regiões)
Chunk C: todas as linhas de clientes Especial (todas as regiões)
```
Isso garante que a pergunta "Qual o SLA para Premium?" recupere o chunk A inteiro — com todas as variantes regionais que o atendente pode precisar na sequência da conversa.

##### Manuais operacionais e procedimentos (perguntas procedurais)

**Problema do chunking por tamanho fixo:**
Um procedimento de 8 passos com 900 tokens é cortado ao meio. A query "como abrir reclamação" recupera o chunk com os passos 1–4 mas não o chunk com os passos 5–8 (que pode não ter score alto o suficiente para entrar no top_k).

**Estratégia correta — chunking por unidade semântica (H3):**
```
Cada seção H3 = um chunk atômico, independente do tamanho
Se seção > 800 tokens → aplicar Parent-Child chunking:
  - Child chunks (~150 tokens por passo) → usados na busca
  - Parent chunk (procedimento completo) → injetado no prompt
```

O **Parent-Child chunking** resolve o dilema diretamente: a busca vetorial usa os filhos pequenos (alta precisão), mas o LLM recebe o pai completo (contexto suficiente para responder).

##### Políticas de compliance e devolução (perguntas condicionais)

**Problema do chunking por tamanho fixo:**
A regra "o cliente pode recusar a entrega se (a) o produto estiver avariado, (b) o lacre estiver violado, ou (c) houver divergência na nota fiscal" pode ser cortada antes das condições. O chunk resultante diz "o cliente pode recusar a entrega se..." — mas os casos seguem em outro chunk.

**Estratégia correta — chunk por artigo de regra:**
```
Cada artigo ou subartigo = um chunk
Nunca cortar entre condição e consequência
Prefixo obrigatório: "[Política de Devolução — Art. 3.2]" como
primeiro token do chunk — ancora o contexto na recuperação
```

O prefixo com o nome da política e artigo melhora o embedding porque ancoa o chunk na semântica do documento de origem, não apenas no conteúdo isolado.

##### Wiki Confluence (conteúdo misto)

**Estratégia correta — chunking por seção semântica com prefixo de título:**
```
chunk = f"[{titulo_da_pagina} > {titulo_da_secao}]\n\n{conteudo_da_secao}"
```

O prefixo `[Procedimento de Reclamação > Prazo para Abertura]` injeta contexto hierárquico no embedding sem precisar de um campo de metadado separado. Isso é especialmente importante no Confluence, onde o título da seção H2 carrega mais semântica do que o conteúdo da seção sozinho.

---

#### Resumo — decisão de chunking por tipo de documento

| Tipo de documento | Estratégia | Tamanho alvo | Técnica especial |
|---|---|---|---|
| Tabelas SLA / frete | Agrupamento por categoria lógica | 400–500 tokens | Serialização em prosa por grupo |
| Manuais / procedimentos curtos | Chunking por seção H3 | 300–700 tokens (variável) | Respeitar fronteira de procedimento |
| Manuais / procedimentos longos | Parent-Child chunking | Child: ~150 tok / Parent: ~700 tok | Busca no filho, injeção do pai |
| Políticas e compliance | Chunking por artigo de regra | 400–600 tokens | Prefixo `[Doc > Artigo]` |
| Wiki Confluence | Chunking semântico por H2/H3 | 400–600 tokens | Prefixo hierárquico de título |

> **Decisão arquitetural:** o pipeline de ingestão deve identificar o tipo de documento e aplicar a estratégia correspondente — não existe estratégia única ótima para todos os formatos da NovaTech.

---

## 7. Viabilidade por Requisito

| Requisito | Viabilidade | Observações |
|---|---|---|
| Respostas rastreáveis (fonte + seção) | Alta | Metadados nos chunks + instrução no prompt para citar fonte |
| Sem alucinações | Média-Alta | RAG reduz alucinações mas não elimina — mitigado com temperature baixa e instrução explícita de "não responda além dos documentos" |
| Atualização mensal das planilhas | Alta | Azure Function com trigger periódico — re-ingestão parcial |
| Cobertura das 3 fontes | Média | SharePoint: fácil; Confluence e rede: requer desenvolvimento de conectores customizados |
| Interface no Teams | Alta | Azure Bot Service + Teams Channel nativo |
| Sem treinamento extensivo | Alta | Interface conversacional no Teams — familiar para os atendentes |

---

## 8. Riscos Técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Qualidade ruim de chunks em PDFs escaneados | Média | Alto | Document Intelligence OCR + revisão manual de amostra |
| Contradições documentais gerando respostas incorretas | Alta | Alto | Governança de conteúdo + instrução de conflito no system prompt |
| Latência elevada na busca + geração | Média | Médio | Cache de queries frequentes + otimização do top_k |
| Conector Confluence indisponível ou instável | Média | Médio | Job de extração assíncrono com retry + alertas |
| Atualização mensal de planilhas não triggerada | Baixa | Alto | Monitoramento do pipeline de ingestão com alertas no Azure Monitor |
| Custo Azure acima do previsto | Média | Médio | Definir limites de orçamento no Azure Cost Management; otimizar top_k e tamanho do prompt |

---

## 9. Stack Tecnológico Recomendado

```
Camada de Interface:    Microsoft Teams (Bot Framework SDK v4 — C# ou Node.js)
Orquestração RAG:       LangChain ou Semantic Kernel (integração nativa com Azure OpenAI)
Busca semântica:        Azure AI Search (índice híbrido: vetorial + BM25 + semantic reranker)
Modelo de geração:      Azure OpenAI — GPT-4o (ou GPT-4.1 quando disponível no Azure)
Embeddings:             Azure OpenAI — text-embedding-3-large
Ingestão:               Azure Functions (triggers agendados e por evento)
Document Intelligence:  Azure AI Document Intelligence (extração de PDFs)
Monitoramento:          Azure Monitor + Application Insights
```

---

## 10. Revisão Crítica — Pontos Fracos, Estimativas e Riscos Não Contemplados

> Esta seção representa uma leitura adversarial do próprio documento, identificando onde a análise é otimista demais, onde faltam dados para sustentar uma conclusão e onde riscos materiais foram omitidos. O objetivo é que esses pontos sejam endereçados antes do início do desenvolvimento.

---

### 10.1 Correções factuais

Erros de fato identificados nas seções anteriores — corrigidos na origem e registrados aqui para rastreabilidade:

| Seção | O que estava incorreto | Valor correto |
|---|---|---|
| §5.5 | "Basic tier suporta até 15 GB" | Basic tier tem **2 GB**. Standard S1 tem 25 GB/partição. A afirmação original estava errada por um fator de 7×. |
| §5.1 | "250 palavras/página descrita como conservadora" | 250 palavras/página é **abaixo da média** para documentos técnico-operacionais (350–500 palavras/página é mais realista). A base pode ser 1,4–2× maior do que estimado. |
| §6.6 | "Reserva para geração: ~500 tokens" | Respostas procedurais completas (8 passos + condições + exceções) exigem 800–1.500 tokens. Corrigido para intervalo de 800–1.500 tokens na v0.2. |

---

### 10.2 Estimativas que merecem validação antes de virar premissa

As estimativas abaixo foram usadas em cálculos de capacidade e custo **sem validação com dados reais** da NovaTech. Se incorretas, impactam diretamente o dimensionamento da solução.

| Estimativa usada | Por que pode ser otimista | Intervalo real provável | Como validar |
|---|---|---|---|
| 800 docs × **média de 10 páginas** | Média não auditada. Manuais operacionais de logística podem ter 50–200 páginas; formulários têm 1. A distribuição não é uniforme. | 8.000–40.000 páginas no total | Inventário no SharePoint: contar páginas reais por documento durante o Discovery |
| **20% de churn mensal** nos documentos | Arbitrário. Em logística, tabelas de SLA e regras de frete mudam sazonalmente. Documentos Comerciais podem ter churn de 40–60% ao ano. | 15–40% dependendo da área | Levantar frequência de atualizações por área (Operações, Compliance, Comercial) no Discovery |
| **U$0,014/query** com GPT-4o | Usa preço de consumo (pay-as-you-go). Sob pico com 45 usuários simultâneos, o Azure OpenAI pode exigir **PTU (Provisioned Throughput Units)**, cobrado por hora independente de uso — elevando o custo em 3–5×. | U$0,014–0,070/query | Simular throughput pico: 45 usuários × 1 query/2min = ~22 req/min → calcular TPM necessário |
| **3 meses** para go-live | Não inclui: (1) aprovação do bot no Teams pelo admin M365, (2) revisão LGPD, (3) conector Confluence do zero (~3–4 semanas), (4) iterações do piloto com atendentes reais. | 4–6 meses para go-live de qualidade | Mapear dependências de aprovação com TI da NovaTech na semana 1 do Discovery |

---

### 10.3 Riscos não contemplados na §8

Os riscos abaixo são materiais para o sucesso do projeto e estavam ausentes da tabela de riscos:

| Risco | Categoria | Probabilidade | Impacto | Por que é relevante |
|---|---|---|---|---|
| **LGPD** — documentos podem conter dados pessoais de clientes | Compliance / Legal | Média | Alto | Indexar dados pessoais em Azure OpenAI/AI Search pode configurar tratamento de dados sem base legal explícita. O DPO da NovaTech precisa ser consultado antes do início do desenvolvimento. |
| **Ausência de controle de acesso granular** — assistente ignora permissões do SharePoint | Segurança | Alta | Alto | Na arquitetura atual, todo atendente recebe respostas baseadas em todos os documentos indexados, incluindo os que não teria acesso direto. Isso pode violar políticas internas e normas de compliance. |
| **Rate limits do Azure OpenAI sob carga concorrente** | Performance | Média | Alto | Um deployment padrão de GPT-4o tem limites de TPM (ex.: 120K TPM no tier S0). Com 45 usuários simultâneos no pico, esse limite pode ser excedido, causando erros 429. Sem retry/queue, o assistente para de responder para todos. |
| **Qualidade do semantic reranker em português** | Qualidade RAG | Alta | Médio | O Azure AI Search semantic reranker foi treinado com predominância em inglês. Em PT-BR a degradação de qualidade é significativa. A decisão de depender do reranker para `top_k` baixo precisa ser validada empiricamente com os documentos reais da NovaTech. |
| **Aprovação de bot corporativo no Microsoft Teams** | Operacional / Timeline | Alta | Médio | Publicar um bot no Teams corporativo exige aprovação do administrador global do M365 e análise de segurança. Esse processo pode levar 2–6 semanas e **bloqueia o início do piloto**. |
| **Depreciação e upgrade de modelos** | Operacional | Certa (longo prazo) | Médio | A Microsoft deprecia versões de modelos no Azure OpenAI com aviso de ~12 meses. A arquitetura não menciona estratégia de upgrade sem downtime nem re-validação da qualidade após troca de modelo. |
| **Comportamento indefinido quando o assistente não encontra resposta** | Experiência do usuário | Certa | Alto | O documento não define o que acontece quando nenhum chunk relevante é recuperado. Sem essa definição no system prompt e na UX, as primeiras respostas erradas ou vazias corroem a confiança dos atendentes antes mesmo do go-live. |

---

### 10.4 Lacunas arquiteturais que precisam ser resolvidas antes do desenvolvimento

| Lacuna | Descrição | Decisão necessária |
|---|---|---|
| **SLA de latência não definido** | A stack RAG completa tem latência real de 3–6 segundos por query: embedding (~50ms) + AI Search (~150ms) + reranker (~250ms) + GPT-4o (~2–5s). Para um atendente em chamada ao vivo, 5 segundos é tempo demais. | Definir target de latência (ex.: p95 < 4s) e validar com PoC de carga antes de comprometer com a interface Teams. |
| **LangChain vs. Semantic Kernel — decisão adiada** | O stack recomenda "LangChain ou Semantic Kernel" como se fossem equivalentes. LangChain é Python; Semantic Kernel é C#/Python. Se o Bot Framework for C#, LangChain não é uma opção viável. Essa ambiguidade é um risco de retrabalho. | Decidir linguagem do backend no início do Sprint 1 — essa escolha condiciona toda a camada de orquestração. |
| **Ausência de estratégia de avaliação (Evals)** | O documento não define como medir se o sistema está funcionando bem após o deploy. Sem métricas quantitativas e dataset de ground truth, é impossível detectar regressões após atualizações de documentos ou troca de modelo. | Definir o pipeline de evals como entregável obrigatório do Discovery — não como item opcional de qualidade. |
| **Janela de 6 turnos pode ser insuficiente para chamados complexos** | Chamados de logística podem envolver múltiplas sub-perguntas encadeadas (atraso → devolução → seguro → novo pedido). Com 6 turnos, contexto inicial é descartado sem preservar entidades-chave (tipo de cliente, região, produto). | Avaliar estratégia híbrida: janela deslizante + extração de entidades-chave persistidas ao longo do chamado. |

---

### 10.5 Mapa de criticidade

| Categoria | Itens | Bloqueantes para go-live | Ação imediata |
|---|---|---|---|
| Erros factuais | 3 | 0 | Corrigidos na v0.2 deste documento |
| Estimativas a validar | 4 | 1 (timeline 3 meses) | Mapear aprovações de TI e LGPD na semana 1 do Discovery |
| Riscos não contemplados | 7 | 3 (LGPD, controle de acesso, rate limits) | LGPD: consultar DPO antes de iniciar; acesso: definir arquitetura de autorização no Discovery |
| Lacunas arquiteturais | 4 | 2 (latência, evals) | Incluir PoC de latência e pipeline de evals como entregáveis do Discovery |

---

## 11. Próximos Passos Sugeridos (por fase)

### Discovery (mês 1)
- [ ] Inventário dos documentos no SharePoint: identificar PDFs escaneados vs. digitais
- [ ] Avaliar rate limits e autenticação da API Confluence
- [ ] Entrevistar 3–5 atendentes para identificar os 10 tipos de consulta mais frequentes
- [ ] Definir KPIs de avaliação da qualidade das respostas (relevância, fidelidade, completude)
- [ ] Construir dataset de avaliação: 50 perguntas + respostas esperadas (ground truth)

### Desenvolvimento (meses 1–3)
- [ ] PoC: indexar SharePoint + 20 perguntas do dataset de avaliação
- [ ] Iterar estratégia de chunking com base nos resultados do PoC
- [ ] Desenvolver conector Confluence
- [ ] Implementar pipeline de serialização de planilhas
- [ ] Integrar com Microsoft Teams
- [ ] Implementar gerenciamento de histórico (janela deslizante)

### Go-live (mês 3)
- [ ] Piloto com 5–10 atendentes
- [ ] Monitoramento de latência, custo e qualidade
- [ ] Rollout para os 45 atendentes

---

*Documento em construção — versão 0.2*
