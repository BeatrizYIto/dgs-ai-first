"""
Avaliação do Pipeline RAG — NovaTech PoC
Valida se o retrieval recupera os chunks corretos conforme o mapa de cobertura do Anexo B.

Como usar:
    python rag_prototype/rag_evaluation.py

Pré-requisito: rodar rag_pipeline.py ao menos uma vez para indexar os documentos.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline import get_collection, load_embedding_model, retrieve, CHROMA_DIR

# ---------------------------------------------------------------------------
# Assinaturas dos chunks de referência (Anexo B)
# Todas as keywords devem aparecer no texto recuperado para o chunk ser reconhecido.
# ---------------------------------------------------------------------------
CHUNK_SIGNATURES: dict[str, list[str]] = {
    # POL-001 — Política de Devolução
    "POL-001-A": ["sete", "dias úteis", "recebimento", "tracking"],
    "POL-001-B": ["classes 1 a 6", "antt", "perigosas"],
    "POL-001-C": ["portal do cliente", "ct-e"],
    "POL-001-D": ["defeito ou erro", "frete reverso"],

    # PROC-042 v1 — fator de peso 1.2 e Norte=1.6
    "PROC-042-A": ["fator de peso", "1.2", "1.001"],
    "PROC-042-B": ["norte", "1.6", "sul", "sudeste"],

    # PROC-042 v2 — fator de peso 1.15 e Norte=1.8
    "PROC-042v2-A": ["fator de peso", "1.15"],
    "PROC-042v2-B": ["norte", "1.8", "sul", "sudeste"],

    # SLA-2024
    "SLA-2024-A": ["três", "tiers", "gold", "silver", "standard"],
    "SLA-2024-B": ["chamados gerais", "2h úteis"],
    "SLA-2024-C": ["incidentes críticos", "30min"],

    # FAQ
    "FAQ-03":  ["ramal 4500", "gestão de riscos"],
    "FAQ-15":  ["platinum"],
    "FAQ-32":  ["frete expresso", "carga perigosa"],
    "FAQ-38":  ["sinistros@novatech"],
}

# ---------------------------------------------------------------------------
# Casos de teste — mapa de cobertura do Anexo B
# must_retrieve: chunks que DEVEM aparecer (falha se ausentes)
# may_retrieve:  chunks que podem aparecer (relevância menor, não obrigatório)
# contradiction: par de chunks que, se recuperados juntos, indica conflito de versão
# expect_no_answer: sinaliza que o pipeline correto NÃO deveria ter cobertura real
# ---------------------------------------------------------------------------
TEST_CASES: list[dict] = [
    {
        "id": 1,
        "query": "Qual o prazo de devolução?",
        "must_retrieve": ["POL-001-A", "POL-001-B"],
        "may_retrieve":  ["POL-001-C"],
        "contradiction": None,
    },
    {
        "id": 2,
        "query": "Posso devolver carga perigosa?",
        "must_retrieve": ["POL-001-B"],
        "may_retrieve":  ["FAQ-03", "POL-001-A"],
        "contradiction": None,
    },
    {
        "id": 3,
        "query": "Qual o SLA do cliente Gold?",
        "must_retrieve": ["SLA-2024-B"],
        "may_retrieve":  ["SLA-2024-A", "SLA-2024-C"],
        "contradiction": None,
    },
    {
        "id": 4,
        "query": "Qual o SLA do cliente Platinum?",
        "must_retrieve": ["SLA-2024-A"],
        "may_retrieve":  ["FAQ-15"],
        "contradiction": None,
    },
    {
        "id": 5,
        "query": "Frete para 600kg para Manaus?",
        "must_retrieve": ["PROC-042v2-B", "PROC-042v2-A"],
        "may_retrieve":  ["PROC-042-B"],
        "contradiction": ("PROC-042-B", "PROC-042v2-B"),
    },
    {
        "id": 6,
        "query": "Frete para 300kg para Salvador?",
        "must_retrieve": [],
        "may_retrieve":  ["PROC-042v2-B"],
        "contradiction": None,
        "expect_no_answer": True,
    },
    {
        "id": 7,
        "query": "O que acontece com carga danificada em trânsito?",
        "must_retrieve": ["FAQ-38"],
        "may_retrieve":  [],
        "contradiction": None,
    },
    {
        "id": 8,
        "query": "Carga perigosa pode ser enviada com frete expresso?",
        "must_retrieve": ["FAQ-32"],
        "may_retrieve":  [],
        "contradiction": None,
    },
    {
        "id": 9,
        "query": "Qual o multiplicador regional para o Sudeste?",
        "must_retrieve": ["PROC-042v2-B"],
        "may_retrieve":  ["PROC-042-B"],
        "contradiction": ("PROC-042-B", "PROC-042v2-B"),
    },
    {
        "id": 10,
        "query": "Prazo de devolução de carga perigosa com frete especial acima de 500kg",
        "must_retrieve": ["POL-001-A", "POL-001-B", "PROC-042v2-A", "PROC-042v2-B"],
        "may_retrieve":  ["FAQ-03"],
        "contradiction": ("PROC-042-B", "PROC-042v2-B"),
    },
]


# ---------------------------------------------------------------------------
# Funções de avaliação
# ---------------------------------------------------------------------------

def identify_chunks(retrieved: list[dict]) -> list[str]:
    """Identifica quais chunks de referência do Anexo B estão nos resultados."""
    found = []
    for chunk in retrieved:
        text = chunk["text"].lower()
        for chunk_id, keywords in CHUNK_SIGNATURES.items():
            if chunk_id not in found and all(kw.lower() in text for kw in keywords):
                found.append(chunk_id)
    return found


def run_evaluation(top_k: int = 5) -> None:
    collection = get_collection(CHROMA_DIR)
    if collection.count() == 0:
        print("[erro] Base vazia. Execute rag_pipeline.py primeiro.")
        return

    model = load_embedding_model()

    print("\n" + "=" * 68)
    print("  AVALIACAO DO PIPELINE RAG — NovaTech PoC")
    print("  Baseado no mapa de cobertura do Anexo B")
    print("=" * 68)

    passed = 0
    total_must = 0
    found_must = 0
    contradictions_found: list[int] = []
    no_answer_with_results: list[int] = []

    for case in TEST_CASES:
        retrieved = retrieve(collection, model, case["query"], top_k=top_k)
        found_ids = identify_chunks(retrieved)

        must = case["must_retrieve"]
        may  = case["may_retrieve"]

        must_hits = {c: (c in found_ids) for c in must}
        may_hits  = {c: (c in found_ids) for c in may}

        case_passed = all(must_hits.values()) if must else True
        if case_passed:
            passed += 1

        total_must += len(must)
        found_must += sum(must_hits.values())

        # detecta contradição de versão
        contradiction_hit = False
        if case.get("contradiction"):
            c_a, c_b = case["contradiction"]
            if c_a in found_ids and c_b in found_ids:
                contradiction_hit = True
                contradictions_found.append(case["id"])

        # detecta recuperação em pergunta sem cobertura esperada
        no_answer_hit = case.get("expect_no_answer") and bool(found_ids)
        if no_answer_hit:
            no_answer_with_results.append(case["id"])

        # --- imprime resultado ---
        status_icon = "PASSOU" if case_passed else "FALHOU"
        print(f"\nCaso {case['id']:02d}: \"{case['query']}\"")

        if must:
            row = "  Obrigatorios: " + "  ".join(
                f"{c} {'[OK]' if v else '[--]'}" for c, v in must_hits.items()
            )
            print(row)

        if may:
            row = "  Opcionais:    " + "  ".join(
                f"{c} {'[OK]' if v else '[ ]'}" for c, v in may_hits.items()
            )
            print(row)

        extras = [c for c in found_ids if c not in must and c not in may]
        if extras:
            print(f"  Extras:        {', '.join(extras)}")

        if not found_ids:
            print("  (nenhum chunk identificado)")

        if contradiction_hit:
            c_a, c_b = case["contradiction"]
            print(f"  [!] CONTRADICAO: recuperou {c_a} (v1) e {c_b} (v2) ao mesmo tempo")

        if no_answer_hit:
            print("  [!] RISCO: pergunta sem cobertura real recuperou chunks — LLM pode alucinar")

        print(f"  => {status_icon}")

    # --- resumo ---
    pct_must = (100 * found_must // total_must) if total_must else 0
    print("\n" + "=" * 68)
    print("  RESUMO")
    print("=" * 68)
    print(f"  Casos testados:     {len(TEST_CASES)}")
    print(f"  Casos aprovados:    {passed}/{len(TEST_CASES)}")
    print(f"  Recall obrigatorio: {found_must}/{total_must} chunks ({pct_must}%)")

    if contradictions_found:
        print(f"\n  [!] Contradicoes nos casos: {contradictions_found}")
        print("      Recomendacao: filtrar chunks pelo documento mais recente")
        print("      quando ambas as versoes do PROC-042 forem recuperadas.")

    if no_answer_with_results:
        print(f"\n  [!] Perguntas sem cobertura real que retornaram chunks: {no_answer_with_results}")
        print("      O LLM precisa de instrucao explicita para dizer 'nao encontrei'.")

    if not contradictions_found and not no_answer_with_results:
        print("\n  Sem problemas criticos detectados.")

    print()


if __name__ == "__main__":
    run_evaluation(top_k=5)
