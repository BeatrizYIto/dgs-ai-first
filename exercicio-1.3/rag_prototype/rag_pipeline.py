"""
Protótipo de Pipeline RAG — NovaTech PoC
Stack: Python + ChromaDB + sentence-transformers + Ollama (LLM local)

Fluxo:
  1. Ingestão  — lê documentos Markdown e divide em chunks
  2. Embedding — gera vetores com sentence-transformers (all-MiniLM-L6-v2)
  3. Indexação — armazena chunks + vetores no ChromaDB (persistido em disco)
  4. Consulta  — recupera chunks relevantes e monta resposta com LLM

Dependências:
  pip install chromadb sentence-transformers ollama

LLM local (gratuito):
  1. Instale o Ollama: https://ollama.com/download
  2. Baixe um modelo leve: ollama pull llama3.2 (ou phi3, gemma2:2b)
  3. Suba o servidor:     ollama serve
"""

import os
import re
import textwrap
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DOCS_DIR = Path(__file__).parent.parent / "docs"         # raiz do projeto
CHROMA_DIR = Path(__file__).parent / "chroma_db" # pasta de persistência
COLLECTION_NAME = "novatech_docs"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"            # modelo leve, ~80 MB

CHUNK_SIZE = 400          # caracteres por chunk
CHUNK_OVERLAP = 80        # sobreposição entre chunks
TOP_K = 4                 # chunks recuperados por consulta

# Extensões de documento suportadas
SUPPORTED_EXTENSIONS = {".md", ".txt"}

# Whitelist: apenas estes 5 arquivos oficiais da NovaTech são ingeridos.
# Deixar vazio {} para ingerir todos os .md da pasta (modo genérico).
TARGET_DOCS = {
    "FAQ-atendimento.md",
    "POL-001-politica-devolucao.md",
    "PROC-042-frete-especial-v1.md",
    "PROC-042-v2-frete-especial-revisado.md",
    "SLA-2024-tabela-sla-clientes.md",
}


# ---------------------------------------------------------------------------
# 1. Ingestão e chunking
# ---------------------------------------------------------------------------

def load_documents(docs_dir: Path) -> list[dict]:
    """Carrega os documentos definidos em TARGET_DOCS da pasta raiz."""
    docs = []
    for ext in SUPPORTED_EXTENSIONS:
        for filepath in docs_dir.rglob(f"*{ext}"):
            if not filepath.is_file():
                continue
            if TARGET_DOCS and filepath.name not in TARGET_DOCS:
                continue
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            docs.append({
                "path": str(filepath.relative_to(docs_dir)),
                "filename": filepath.name,
                "text": text,
            })
    return docs


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE,
                      overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Divide texto em chunks por parágrafos, respeitando chunk_size.
    Adiciona sobreposição para preservar contexto entre chunks adjacentes.
    """
    # Divide em parágrafos (linhas em branco)
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Se adicionar este parágrafo excede o limite, fecha o chunk atual
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            # sobreposição: mantém o final do chunk anterior
            current = current[-overlap:] + "\n\n" + para
        else:
            current = (current + "\n\n" + para) if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def prepare_chunks(docs: list[dict]) -> list[dict]:
    """Divide todos os documentos em chunks e adiciona metadados."""
    all_chunks = []
    for doc in docs:
        chunks = split_into_chunks(doc["text"])
        for i, chunk_text in enumerate(chunks):
            all_chunks.append({
                "id": f"{doc['path'].replace(os.sep, '/')}::chunk_{i}",
                "text": chunk_text,
                "source": doc["path"],
                "filename": doc["filename"],
                "chunk_index": i,
            })
    return all_chunks


# ---------------------------------------------------------------------------
# 2. Embeddings
# ---------------------------------------------------------------------------

def load_embedding_model() -> SentenceTransformer:
    """Carrega o modelo de embedding (faz download automático na 1ª vez)."""
    print(f"[embedding] Carregando modelo '{EMBEDDING_MODEL}'...")
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(model: SentenceTransformer, texts: list[str]) -> list[list[float]]:
    """Gera embeddings para uma lista de textos."""
    vectors = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    return vectors.tolist()


# ---------------------------------------------------------------------------
# 3. Vector Store (ChromaDB)
# ---------------------------------------------------------------------------

def get_collection(persist_dir: Path) -> chromadb.Collection:
    """Inicializa (ou reabre) a coleção ChromaDB persistida em disco."""
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def index_chunks(collection: chromadb.Collection,
                 model: SentenceTransformer,
                 chunks: list[dict],
                 batch_size: int = 64) -> None:
    """Indexa todos os chunks no ChromaDB em batches."""
    total = len(chunks)
    print(f"[index] Indexando {total} chunks em batches de {batch_size}...")

    for start in range(0, total, batch_size):
        batch = chunks[start:start + batch_size]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [{"source": c["source"], "filename": c["filename"],
                      "chunk_index": c["chunk_index"]} for c in batch]

        embeddings = embed_texts(model, texts)
        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(f"  {min(start + batch_size, total)}/{total} chunks indexados")

    print("[index] Indexação concluída.")


# ---------------------------------------------------------------------------
# 4. Retrieval
# ---------------------------------------------------------------------------

def retrieve(collection: chromadb.Collection,
             model: SentenceTransformer,
             query: str,
             top_k: int = TOP_K) -> list[dict]:
    """Recupera os chunks mais relevantes para a consulta."""
    query_vector = embed_texts(model, [query])[0]
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source": meta["source"],
            "filename": meta["filename"],
            "score": round(1 - dist, 4),  # cosine similarity (0–1)
        })
    return chunks


# ---------------------------------------------------------------------------
# 5. Geração de resposta
# ---------------------------------------------------------------------------

def build_prompt(query: str, context_chunks: list[dict]) -> str:
    """Monta o prompt com contexto para enviar ao LLM."""
    context_blocks = []
    for i, chunk in enumerate(context_chunks, 1):
        context_blocks.append(
            f"[Fonte {i}: {chunk['source']} — relevância {chunk['score']}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_blocks)

    return f"""Você é o assistente de IA da NovaTech, especialista em logística.
Responda à pergunta SOMENTE com base nas fontes fornecidas abaixo.
Se a informação não estiver nas fontes, diga que não encontrou na documentação disponível.
Ao final da resposta, cite as fontes usadas.

=== FONTES ===
{context}

=== PERGUNTA ===
{query}

=== RESPOSTA ==="""


def generate_with_ollama(prompt: str, model: str = "llama3.2") -> str:
    """Gera resposta usando Ollama (LLM local). Requer `ollama serve` rodando."""
    try:
        import ollama
        response = ollama.generate(model=model, prompt=prompt)
        return response["response"]
    except ImportError:
        return "[ERRO] Pacote 'ollama' não instalado. Execute: pip install ollama"
    except Exception as e:
        return f"[ERRO ao chamar Ollama] {e}\n\nDica: execute 'ollama serve' e 'ollama pull llama3.2'"


def answer_without_llm(query: str, context_chunks: list[dict]) -> str:
    """
    Fallback sem LLM: retorna os chunks relevantes diretamente.
    Útil para testar o pipeline de retrieval sem dependência de LLM.
    """
    lines = [f"Pergunta: {query}\n", "Trechos mais relevantes encontrados:\n"]
    for i, chunk in enumerate(context_chunks, 1):
        lines.append(f"\n--- Fonte {i}: {chunk['source']} (score: {chunk['score']}) ---")
        lines.append(textwrap.fill(chunk["text"], width=100))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Interface principal
# ---------------------------------------------------------------------------

def ingest(force_reindex: bool = False) -> tuple[chromadb.Collection, SentenceTransformer]:
    """Executa a fase de ingestão + indexação."""
    collection = get_collection(CHROMA_DIR)
    model = load_embedding_model()

    existing_count = collection.count()
    if existing_count > 0 and not force_reindex:
        print(f"[ingest] Base já indexada com {existing_count} chunks. "
              "Use force_reindex=True para reindexar.")
        return collection, model

    print("[ingest] Carregando documentos...")
    docs = load_documents(DOCS_DIR)
    if not docs:
        print("[ingest] Nenhum documento encontrado em", DOCS_DIR)
        return collection, model

    print(f"[ingest] {len(docs)} documentos encontrados:")
    for d in docs:
        print(f"  • {d['path']}")

    chunks = prepare_chunks(docs)
    print(f"[ingest] {len(chunks)} chunks gerados.")

    index_chunks(collection, model, chunks)
    return collection, model


def query(question: str,
          use_llm: bool = True,
          llm_model: str = "llama3.2") -> None:
    """Consulta o pipeline RAG e imprime a resposta."""
    collection = get_collection(CHROMA_DIR)
    if collection.count() == 0:
        print("[query] Base vazia. Execute ingest() primeiro.")
        return

    model = load_embedding_model()

    print(f"\n{'='*60}")
    print(f"Pergunta: {question}")
    print("="*60)

    chunks = retrieve(collection, model, question)

    if use_llm:
        prompt = build_prompt(question, chunks)
        print("\n[gerando resposta com LLM...]\n")
        answer = generate_with_ollama(prompt, model=llm_model)
        print(answer)
    else:
        print(answer_without_llm(question, chunks))

    print(f"\n{'='*60}\n")


# ---------------------------------------------------------------------------
# Demo — executar diretamente com: python rag_pipeline.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n=== PROTÓTIPO RAG — NovaTech PoC ===\n")

    # --- Fase 1: Ingestão ---
    print(">> Fase 1: Ingestão e indexação de documentos")
    ingest()

    # --- Fase 2: Consultas de teste ---
    print("\n>> Fase 2: Consultas de teste\n")

    test_questions = [
        "Qual o prazo de devolução?",
        "Posso devolver carga perigosa?",
        "Qual o SLA do cliente Gold",
        "Frete para 600kg para Manaus?",
        "Qual o multiplicador para o Sudeste?"
    ]

    for question in test_questions:
        # use_llm=False para testar sem LLM instalado
        # Troque para use_llm=True se tiver o Ollama rodando
        query(question, use_llm=False)

    print("\nPara testar com LLM local:")
    print("  1. Instale: pip install ollama")
    print("  2. Execute:  ollama serve")
    print("  3. Baixe:    ollama pull llama3.2")
    print("  4. Chame:    query('sua pergunta', use_llm=True)")
    print("\nRodar novamente: python exercicio-1.3/rag_prototype/rag_pipeline.py")
