# Skill Tree — NovaTech Assistant

Hierarquia de skills seguindo o fluxo **Foundation → Domain → Artifact**.  
Skills de camadas superiores devem ser lidos antes dos de camadas inferiores.

---

## Foundation — Convenções globais

Pré-requisito para todos os outros skills. Define as regras que valem em todo o repositório.

| Skill | Arquivo | Quem cria | Quem consome | Frequência estimada |
|-------|---------|-----------|--------------|---------------------|
| TypeScript Conventions | `foundation/typescript-conventions.md` | Tech Lead | Todo desenvolvedor; Claude Code ao gerar qualquer arquivo `.ts` | Muito alta — toda geração de código |
| Project Structure | `foundation/project-structure.md` | Tech Lead | Todo desenvolvedor; Claude Code ao decidir onde criar um arquivo | Muito alta — toda nova feature |
| Error Handling | `foundation/error-handling.md` | Tech Lead | Todo desenvolvedor; Claude Code ao gerar services e handlers | Muito alta — todo service e handler |
| Logging | `foundation/logging.md` | Tech Lead | Todo desenvolvedor; Claude Code ao gerar qualquer função com I/O | Alta — todo código com chamadas externas ou erros |
| Env Config | `foundation/env-config.md` | Tech Lead | Todo desenvolvedor; Claude Code ao criar serviços ou testes | Média — ao introduzir nova integração ou configuração |

---

## Domain — Padrões por camada

Específicos de uma camada ou tecnologia. Requerem os skills de Foundation como base.

| Skill | Arquivo | Quem cria | Quem consome | Frequência estimada |
|-------|---------|-----------|--------------|---------------------|
| Azure Functions Endpoint | `domain/azure-functions-endpoint.md` | Tech Lead | Dev Backend; Claude Code ao gerar `src/functions/**` | Alta — todo novo endpoint HTTP |
| Azure AI Search Integration | `domain/azure-ai-search-integration.md` | Tech Lead | Dev Backend; Claude Code ao gerar `src/services/search.ts` | Média — ao implementar ou alterar a camada de busca vetorial |
| Testing Patterns | `domain/testing-patterns.md` | QA | Todo desenvolvedor; Claude Code ao gerar qualquer `*.test.ts` | Alta — todo novo módulo tem testes correspondentes |
| React Component Patterns | `domain/react-components.md` | Tech Lead / Frontend Dev | Frontend Dev; Claude Code ao gerar `src/web/` ou `src/bot/cards/` | Baixa — restrita ao painel web e bot do Teams |

---

## Artifact — Receitas de geração

Receitas end-to-end que orquestram skills de Foundation e Domain em passos concretos.  
Cada skill desta camada lista explicitamente seus pré-requisitos.

| Skill | Arquivo | Quem cria | Quem consome | Frequência estimada |
|-------|---------|-----------|--------------|---------------------|
| Create RAG Endpoint | `artifact/create-rag-endpoint.md` | Tech Lead | Dev Backend; Claude Code ao implementar um endpoint de consulta RAG | Baixa — uma vez por endpoint RAG criado |
| Create Integration Test | `artifact/create-integration-test.md` | QA | QA, Dev Backend; Claude Code ao escrever testes de integração para um handler | Média — uma vez por handler implementado |
| Create React Card | `artifact/create-react-card.md` | Tech Lead / Frontend Dev | Frontend Dev; Claude Code ao criar componentes de card no dashboard | Baixa — uma vez por componente de card |

---

## Grafo de dependências

```
Foundation
├── typescript-conventions  ←── base de todo o resto
├── project-structure       ←── base de todo o resto
├── error-handling          ←── base de services e handlers
├── logging                 ←── base de todo código com I/O
└── env-config              ←── base de serviços e testes

Domain (requer Foundation)
├── azure-functions-endpoint        usa: typescript-conventions, error-handling, logging
├── azure-ai-search-integration     usa: typescript-conventions, error-handling, logging, env-config
├── testing-patterns                usa: typescript-conventions, error-handling, env-config
└── react-components                usa: typescript-conventions

Artifact (requer Foundation + Domain)
├── create-rag-endpoint     usa: typescript-conventions, error-handling, logging, env-config,
│                                azure-functions-endpoint, azure-ai-search-integration
├── create-integration-test usa: testing-patterns, error-handling
└── create-react-card       usa: react-components, typescript-conventions
```

---

## Papéis

| Papel | Responsabilidade sobre skills |
|-------|-------------------------------|
| **Tech Lead** | Cria e mantém os skills de Foundation e a maioria dos skills de Domain e Artifact |
| **QA** | Cria e mantém `testing-patterns` e `create-integration-test` |
| **Frontend Dev** | Co-cria `react-components` e `create-react-card` |
| **Todo Dev** | Consome os skills ao implementar; sinaliza quando um skill está desatualizado |
| **Claude Code / copilot** | Consome automaticamente o skill mais específico que corresponde à frase do prompt |
