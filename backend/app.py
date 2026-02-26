import os
import httpx
import asyncio
import re
from typing import List, Dict, Any
from .pdf_utils import clean_ocr_text  

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    def count_tokens(text: str) -> int:
        # rough approximation: 1 token ~= 4 characters
        return len(text) // 4


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

def get_rag_engine():
    from .rag_engine import get_rag_engine as _get_rag_engine
    return _get_rag_engine()

def clean_for_display(text: str) -> str:
    """
    Apply OCR cleaning and additional fixes for display:
    - Remove unwanted characters, normalize whitespace.
    - Insert space after period followed by uppercase.
    - Insert space between lowercase and uppercase (merged words).
    """
    cleaned = clean_ocr_text(text)
    # Insert space after period if followed directly by uppercase letter
    cleaned = re.sub(r'\.([A-Z])', r'. \1', cleaned)
    # Insert space between lowercase and uppercase (e.g., "wordWORD" -> "word WORD")
    cleaned = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', cleaned)
    # Collapse multiple spaces
    return ' '.join(cleaned.split())

async def generate_with_context(query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """
    Generate response using context. More permissive prompt to extract information.
    """
    if not context_chunks:
        return "No relevant information found in the document."

    MAX_CONTEXT_TOKENS = 6000
    included = []
    total_tokens = 0
    chunks_to_iterate = sorted(context_chunks, key=lambda x: x.get("similarity", 0), reverse=True)
    for c in chunks_to_iterate:
        text = c['text']
        tok = count_tokens(text)
        if total_tokens + tok > MAX_CONTEXT_TOKENS:
            remaining = MAX_CONTEXT_TOKENS - total_tokens
            if remaining > 0:
                text = text[: remaining * 4]
                included.append((c['metadata']['page'], text))
                total_tokens += count_tokens(text)
            break
        included.append((c['metadata']['page'], text))
        total_tokens += tok

    context_text = "\n\n".join([
        f"[Page {page}]: {txt}" for page, txt in included
    ])
    print(f"[debug] built context with approx {total_tokens} tokens ({len(included)} chunks)")


    prompt = f"""You are an assistant that answers questions based SOLELY on the provided context.

    CONTEXT (document fragments):
    {context_text}

    INSTRUCTIONS:
    - Use the context information to answer the question.
    - If the context contains relevant information, answer with it, indicating the page in brackets [Page X].
    - If the context partially mentions the topic, you can say "The text mentions [topic] on pages..." and summarize what it says.
    - If there is NOTHING in the context that answers the question, respond with "I couldn't find this information in the text."
    - Do NOT invent anything that is not in the context.

    QUESTION: {query}

    ANSWER:"""
    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 512},
        }
        try:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            model_text = data.get("response", "").strip()
            low = model_text.lower()

            # If model explicitly says it couldn't find the info, perform a simple keyword fallback
            if ("couldn't find" in low or "could not find" in low or
                "i couldn't find" in low or "i could not find" in low or
                "couldn't locate" in low):
                terms = [t for t in re.findall(r"\w{3,}", query.lower()) if len(t) > 2]
                matches = []
                for c in context_chunks:
                    txt = c.get('text', '')
                    lowtxt = txt.lower()
                    if any(t in lowtxt for t in terms):
                        snippet = clean_for_display(txt)
                        if len(snippet) > 300:
                            snippet = snippet[:300].rsplit(' ', 1)[0] + '...'
                        matches.append((c['metadata'].get('page'), snippet))
                        if len(matches) >= 6:
                            break
                if matches:
                    parts = [f"[Page {p}]: {s}" for p, s in matches]
                    return "I found the following passages in the document that mention your query:\n\n" + "\n\n".join(parts)
                # nothing found, return model's original message
            return model_text
        except Exception as e:
            print(f"[ERROR] generate_with_context: {e}")
            return f"Error generating answer: {e}"