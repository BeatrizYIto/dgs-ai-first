# Contexto do Projeto — Assistente de IA NovaTech

**Cliente:** NovaTech | **Fornecedor:** DB1 | **Versão:** 1.1

---

## 1. Sobre o Cliente

A **NovaTech** é uma empresa de médio porte do setor de **logística**, com **1.200 funcionários**. Sua operação depende intensamente de documentação interna estruturada, que inclui:

- Manuais de procedimento operacional
- Políticas de compliance
- Tabelas de SLA por tipo de cliente
- Regras de cálculo de frete
- Normas de segurança de carga

---

## 2. Fontes de Documentação Existentes

| Fonte                       | Tipo                    | Volume             |
| --------------------------- | ----------------------- | ------------------ |
| SharePoint corporativo      | PDFs e documentos Word  | ~800 documentos    |
| Wiki interna (Confluence)   | Páginas de conhecimento | ~400 páginas       |
| Pasta de rede compartilhada | Planilhas de referência | Atualização mensal |

> ⚠️ **Problema estrutural:** a documentação está fragmentada em três ambientes distintos, sem uma interface unificada de consulta.

---

## 3. Problema de Negócio

### Equipe afetada

- **Time de Atendimento ao Cliente:** 45 atendentes

### Situação atual

Os atendentes precisam consultar manualmente as três fontes acima para responder dúvidas de clientes sobre:

- Prazos de entrega
- Regras de cálculo de frete
- Políticas de devolução
- Procedimentos de reclamação

### Volume operacional

- **Chamados por dia:** ~320
- **Chamados que envolvem consulta a documentação:** ~60% (~192/dia)

### Impactos mensuráveis

- **Tempo médio de busca por chamado:** ~12 minutos
- **Respostas inconsistentes** entre atendentes (cada um encontra — ou não encontra — informações diferentes)
- **Frustração** dos atendentes e dos clientes
- **Atrasos** no fechamento de chamados

### Fator agravante — contradição entre documentos

Algumas versões de documentos se contradizem entre si. A equipe de atendimento contorna isso informalmente, perguntando diretamente a colegas com mais experiência. Esse padrão é frágil, não escalável e gera dependência de conhecimento tácito individual.

---

## 4. Solução Contratada

A **DB1** foi contratada para construir um **assistente de IA conversacional** com as seguintes características:

### Funcionalidade central

- Receber perguntas em **linguagem natural** dos atendentes
- Retornar respostas **fundamentadas na documentação oficial** da NovaTech
- **Indicar a fonte** de cada resposta (documento, página, seção)

### Infraestrutura disponível

- **Licenciamento:** Microsoft 365 E3 (já provisionado)
- **Serviços de IA:** Azure AI Services — a NovaTech está disposta a provisionar
- Isso posiciona o projeto naturalmente sobre o stack **Azure OpenAI + Azure AI Search + SharePoint/Teams**

### Integração de ambiente

O assistente será integrado ao ecossistema **Microsoft 365** da NovaTech:

- **Microsoft Teams** — interface de uso pelos atendentes
- **SharePoint** — fonte primária de documentos (PDFs e Word)

### Prazo e orçamento

- **Duração total:** 3 meses
- **Fases previstas:** Discovery → Desenvolvimento → Go-live

---

## 5. Requisitos Implícitos e Restrições

| Categoria                  | Detalhe                                                                                                                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Confiabilidade**         | Respostas devem ser rastreáveis até a fonte oficial; sem alucinações                                                                                                                             |
| **Atualização de dados**   | Planilhas de rede são atualizadas mensalmente — o sistema deve refletir isso                                                                                                                     |
| **Cobertura**              | Todas as três fontes (SharePoint, Confluence, pasta de rede) devem ser indexadas                                                                                                                 |
| **Usabilidade**            | Interface simples o suficiente para uso no fluxo de atendimento, sem treinamento extensivo                                                                                                       |
| **Ambiente Microsoft**     | Preferência por soluções compatíveis com o stack M365 já adotado                                                                                                                                 |
| **Governança de conteúdo** | Documentação é mantida por 3 áreas distintas (Operações, Compliance, Comercial) sem processo unificado de revisão — há risco de contradições entre versões que o assistente precisa saber tratar |

---

## 6. Métricas de Sucesso Esperadas

| Métrica                          | Baseline atual                  | Meta (diretoria)                      |
| -------------------------------- | ------------------------------- | ------------------------------------- |
| Tempo médio de busca por chamado | ~12 minutos                     | < 2 minutos                           |
| Consistência de respostas        | Variável (depende do atendente) | Padronizada pela documentação oficial |
| Rastreabilidade das respostas    | Nenhuma                         | 100% com indicação de fonte           |
| Adoção pela equipe               | —                               | 45 atendentes ativos no assistente    |

> 💡 **Impacto projetado:** com ~192 chamados/dia envolvendo consulta a documentação e uma redução de 10 min por chamado, a meta representa uma economia estimada de **~32 horas/dia** no time de atendimento.

---

## 7. Stakeholders Relevantes

| Papel                                    | Área                                                                   |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| Usuários finais                          | Equipe de Atendimento ao Cliente (45 pessoas)                          |
| Administradores de conteúdo — Operações  | Manutenção de manuais de procedimento e normas de segurança            |
| Administradores de conteúdo — Compliance | Manutenção de políticas de compliance e normas regulatórias            |
| Administradores de conteúdo — Comercial  | Manutenção de tabelas de SLA, regras de frete e políticas de devolução |
| Patrocinador do projeto                  | Liderança de operações / TI da NovaTech                                |
| Fornecedor de desenvolvimento            | DB1                                                                    |

---

## 8. Glossário Rápido

| Termo          | Definição no contexto                                                                                                                           |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **SLA**        | Acordo de Nível de Serviço — prazo e qualidade garantidos por tipo de cliente                                                                   |
| **Chamado**    | Registro de atendimento aberto por um cliente                                                                                                   |
| **RAG**        | Retrieval-Augmented Generation — arquitetura de IA que combina busca em documentos com geração de resposta; abordagem natural para este projeto |
| **Confluence** | Plataforma de wiki corporativa (Atlassian) usada pela NovaTech                                                                                  |
| **SharePoint** | Plataforma de gestão de documentos da Microsoft usada pela NovaTech                                                                             |
