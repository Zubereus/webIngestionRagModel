from dataclasses import dataclass
from typing import Any
import httpx

OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_GEN_MODEL = "qwen2.5:1.5b"


@dataclass
class RAGResponse:
    answer: str
    sources: list[dict[str, Any]]


def generate_rag_answer(
    query: str,
    retrieved_chunks: list[dict[str, Any]],
    model: str = DEFAULT_GEN_MODEL,
    api_base: str = OLLAMA_API_BASE,
) -> RAGResponse:
    """
    Format prompt with retrieved context chunks, call Qwen via Ollama,
    and return answer with source citations.
    """
    if not retrieved_chunks:
        return RAGResponse(
            answer="No relevant documents found in the selected collection.",
            sources=[],
        )

    # 1. Assemble context blocks
    context_blocks = []
    sources = []

    for idx, chunk in enumerate(retrieved_chunks, start=1):
        meta = chunk.get("metadata", {})
        title = meta.get("title", "Untitled")
        url = meta.get("url", "")
        text = chunk.get("text", "")
        section = " > ".join(meta.get("section_path", [])) if isinstance(meta.get("section_path"), list) else meta.get("section_path", "")

        context_blocks.append(
            f"[{idx}] Title: {title}\nSection: {section}\nURL: {url}\nContent:\n{text}"
        )
        sources.append({
            "index": idx,
            "title": title,
            "url": url,
            "section": section,
        })

    full_context = "\n\n---\n\n".join(context_blocks)

    system_prompt = (
        "You are an accurate, helpful AI research assistant powered by Qwen. "
        "Answer the user's question based STRICTLY on the provided context chunks below.\n"
        "Guidelines:\n"
        "1. Cite your sources using [1], [2], etc., matching the numbered context blocks.\n"
        "2. If the answer cannot be determined from the provided context, state clearly: "
        "'I cannot find the answer in the provided documents.' Do not fabricate facts.\n"
        "3. Keep answers concise, factual, and well-structured."
    )

    user_prompt = (
        f"Context Information:\n"
        f"{full_context}\n\n"
        f"Question: {query}\n\n"
        f"Answer:"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,  # Low temperature for factual RAG answers
        },
    }

    url = f"{api_base}/api/chat"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        answer_text = result["message"]["content"]

    return RAGResponse(answer=answer_text, sources=sources)
