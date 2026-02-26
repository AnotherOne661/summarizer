import httpx
from typing import List, Dict, Any
import os
import json

async def summarize_segments(segments: List[str], ollama_url: str, ollama_model: str, count_tokens, filename: str, file_id: str, upload_folder: str) -> (List[str], str):
    """
    Summarize each segment and recursively combine into a final summary.
    Returns (summaries, final_summary)
    """
    summaries: List[str] = []
    for i, segment in enumerate(segments):
        prompt = f"""Provide a detailed summary of the following book fragment. Capture the main events, characters, and important details. Be thorough but do not invent anything. Use only the information present in the text.

Fragment:
{segment}

Detailed summary:"""
        timeout = httpx.Timeout(360.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 800},
            }
            try:
                resp = await client.post(f"{ollama_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                summaries.append(data.get("response", ""))
            except Exception as e:
                print(f"Error summarizing segment {i+1}: {e}")
                summaries.append(f"[Error summarizing segment {i+1}]")

    async def make_final_summary(parts: List[str]) -> str:
        combined = "\n\n".join([f"PART {i+1}:\n{s}" for i, s in enumerate(parts)])
        if count_tokens(combined) < 3500:
            final_prompt = f"""From the following detailed summaries of a book (in order), write a comprehensive final summary. Capture the overall plot, character arcs, and key themes. Be thorough and coherent. Do not add anything not present in the summaries.

{combined}

Comprehensive final summary:"""
            timeout = httpx.Timeout(1800.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                payload = {
                    "model": ollama_model,
                    "prompt": final_prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 2000},
                }
                try:
                    resp = await client.post(f"{ollama_url}/api/generate", json=payload)
                    resp.raise_for_status()
                    final_data = resp.json()
                    return final_data.get("response", "")
                except Exception as e:
                    print(f"Error generating final summary: {e}")
                    return "Error generating final summary."
        else:
            mid = len(parts) // 2
            first = await make_final_summary(parts[:mid])
            second = await make_final_summary(parts[mid:])
            return await make_final_summary([first, second])

    final_summary = await make_final_summary(summaries)

    # Save the per-segment summaries to a cache file for later retrieval
    summary_cache_dir = os.path.join(upload_folder, "_summary_cache")
    os.makedirs(summary_cache_dir, exist_ok=True)
    cache_path = os.path.join(summary_cache_dir, f"{file_id}_summaries.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"summaries": summaries, "filename": filename}, f)
    except Exception as e:
        print(f"[WARN] Could not write summary cache: {e}")
    return summaries, final_summary

