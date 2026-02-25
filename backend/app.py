import os
import uuid
import httpx
import asyncio
import re
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
from typing import List, Dict, Any
import shutil
from datetime import datetime

from rag_engine import get_rag_engine

app = FastAPI(title="PDF Summarizer RAG v2", version="2.1")

# Configuración
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/app/uploads")  # Valor por defecto para Docker
COLLECTION_NAME = "pdf_documents"

rag = get_rag_engine()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def clean_ocr_text(text: str) -> str:
    """Limpieza mejorada para OCR con separación de palabras pegadas."""
    if not text:
        return ""
    
    # Insertar espacio entre palabra y palabra con mayúscula (ej. "GOODYTWOSHOES.food" -> "GOODYTWOSHOES. food")
    text = re.sub(r'(?<=[a-záéíóúüñ])(?=[A-ZÁÉÍÓÚÜÑ])', ' ', text)
    text = re.sub(r'(?<=[A-ZÁÉÍÓÚÜÑ])(?=[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ])', ' ', text)
    
    # Eliminar caracteres no deseados
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\'\"]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.{2,}', '.', text)
    return text.strip()

def ocr_image(image):
    """OCR con idiomas español e inglés"""
    return pytesseract.image_to_string(image, lang='spa+eng')

async def extract_pdf_chunks(file_path: str, filename: str) -> List[Dict[str, Any]]:
    """
    Extrae chunks de páginas, aplica limpieza y maneja páginas sin texto.
    """
    reader = PdfReader(file_path)
    chunks = []
    
    print(f"📄 Procesando PDF: {filename} ({len(reader.pages)} páginas)")
    
    for page_num in range(len(reader.pages)):
        print(f"  Página {page_num + 1}/{len(reader.pages)}")
        page = reader.pages[page_num]
        page_text = page.extract_text()
        
        # Si no hay texto, aplicar OCR con mayor resolución
        if not page_text or not page_text.strip():
            print(f"    ↳ Aplicando OCR...")
            images = convert_from_bytes(
                open(file_path, "rb").read(),
                first_page=page_num+1,
                last_page=page_num+1,
                dpi=400  
            )
            if images:
                page_text = ocr_image(images[0])
        
        if page_text:
            page_text = clean_ocr_text(page_text)
        
        if page_text and len(page_text) > 50:
            chunks.append({
                "text": page_text,
                "page": page_num + 1
            })
        else:
            # Página sin contenido legible
            chunks.append({
                "text": f"[Página {page_num + 1} sin contenido legible]",
                "page": page_num + 1
            })
    
    print(f"✓ PDF procesado: {len(chunks)} chunks generados")
    return chunks

async def generate_with_context(query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """
    Genera respuesta usando el contexto. Prompt más permisivo para extraer información.
    """
    if not context_chunks:
        return "No hay información relevante en el documento."
    
    context_text = "\n\n".join([
        f"[Página {c['metadata']['page']}]: {c['text']}" 
        for c in context_chunks
    ])
    
    prompt = f"""Eres un asistente que responde preguntas basándote ÚNICAMENTE en el contexto proporcionado.

CONTEXTO (fragmentos del documento):
{context_text}

INSTRUCCIONES:
- Utiliza la información del contexto para responder a la pregunta.
- Si el contexto contiene información relevante, responde con ella, indicando la página entre corchetes [Página X].
- Si el contexto menciona parcialmente el tema, puedes decir "El texto menciona a [tema] en las páginas..." y resumir lo que dice.
- Si no hay NADA en el contexto que responda a la pregunta, responde "No encuentro esta información en el texto."
- NO inventes nada que no esté en el contexto.

PREGUNTA: {query}

RESPUESTA:"""

    timeout = httpx.Timeout(60.0, connect=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 600,
                "top_k": 10,
                "repeat_penalty": 1.2
            }
        }
        
        try:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except Exception as e:
            print(f"Error generando respuesta: {e}")
            return "Error procesando la solicitud con el modelo de IA."
# ============================================================
# ENDPOINTS DE LA API
# ============================================================

@app.get("/")
async def root():
    return {
        "message": "PDF Summarizer API con RAG v2.1",
        "ollama_model": OLLAMA_MODEL,
        "endpoints": [
            "/upload - Subir PDF",
            "/ask - Hacer preguntas",
            "/summarize/{file_id} - Generar resumen",
            "/documents - Listar documentos",
            "/delete/{file_id} - Eliminar documento",
            "/stats - Estadísticas",
            "/debug/chunks/{file_id} - Ver chunks",
            "/debug/search - Probar búsqueda",
            "/debug/embedding - Probar embeddings",
            "/debug/extract - Ver extracción"
        ]
    }

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    file_id = str(uuid.uuid4())
    temp_pdf = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
    content = await file.read()
    
    with open(temp_pdf, "wb") as f:
        f.write(content)
    
    try:
        chunks = await extract_pdf_chunks(temp_pdf, file.filename)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No se pudo extraer texto del PDF")
        
        num_chunks = rag.add_document_chunks(
            collection_name=COLLECTION_NAME,
            chunks=chunks,
            file_id=file_id,
            filename=file.filename
        )
        
        return JSONResponse(content={
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "message": "PDF procesado e indexado correctamente",
            "stats": {
                "chunks": num_chunks,
                "pages": len(set(c["page"] for c in chunks))
            }
        })
    
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

@app.post("/ask")
async def ask_question(file_id: str = Form(...), question: str = Form(...)):
    if not question:
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")
    
    print(f" Pregunta: {question}")
    print(f" File ID: {file_id}")
    
    relevant_chunks = rag.find_relevant_chunks(
        collection_name=COLLECTION_NAME,
        query=question,
        top_k=15,
        file_id_filter=file_id
    )
    
    if not relevant_chunks:
        return JSONResponse(content={
            "question": question,
            "answer": "No encontré información relevante en el documento para responder esta pregunta.",
            "sources": []
        })
    
    answer = await generate_with_context(question, relevant_chunks)
    
    sources = [
        {
            "page": c["metadata"]["page"],
            "text_preview": c["text"][:200] + "...",
            "similarity": round(c["similarity"], 3)
        }
        for c in relevant_chunks
    ]
    
    return JSONResponse(content={
        "question": question,
        "answer": answer,
        "sources": sources
    })

@app.post("/summarize/{file_id}")
async def summarize_document(file_id: str):
    print(f" Generando resumen para: {file_id}")
    
    all_chunks = rag.find_relevant_chunks(
        collection_name=COLLECTION_NAME,
        query="",  # Consulta vacía para recuperar chunks
        top_k=100,
        file_id_filter=file_id
    )
    
    if not all_chunks:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Ordenar por página
    all_chunks.sort(key=lambda x: x["metadata"]["page"])
    
    # Agrupar en segmentos de tamaño razonable (aprox 2000 caracteres)
    segments = []
    current_segment = []
    current_length = 0
    
    for chunk in all_chunks:
        chunk_len = len(chunk["text"])
        if current_length + chunk_len > 2000 and current_segment:
            segments.append(" ".join(current_segment))
            current_segment = [chunk["text"]]
            current_length = chunk_len
        else:
            current_segment.append(chunk["text"])
            current_length += chunk_len
    
    if current_segment:
        segments.append(" ".join(current_segment))
    
    print(f"  Generando {len(segments)} resúmenes parciales...")
    
    # Resumir cada segmento con prompt estricto
    summaries = []
    for i, segment in enumerate(segments):
        print(f"    Segmento {i+1}/{len(segments)}")
        
        prompt = f"""Extrae los hechos principales del siguiente fragmento de un libro. Sé conciso y usa SOLO la información presente. NO inventes nombres ni eventos.

Fragmento:
{segment}

Hechos extraídos:"""
        
        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 400}
            }
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            data = resp.json()
            summaries.append(data.get("response", ""))
    
    # Resumen final combinando
    print("  Generando resumen final...")
    combined = "\n\n".join([f"PARTE {i+1}: {s}" for i, s in enumerate(summaries)])
    final_prompt = f"""A partir de los siguientes resúmenes parciales de un libro (en orden), escribe un resumen final coherente. Si hay información contradictoria, menciónala. NO añadas nada que no esté en los resúmenes.

{combined}

Resumen final (basado estrictamente en los resúmenes):"""
    
    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": final_prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 800}
        }
        resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        final_data = resp.json()
    
    filename = all_chunks[0]["metadata"]["filename"] if all_chunks else "desconocido"
    
    return JSONResponse(content={
        "file_id": file_id,
        "filename": filename,
        "summary": final_data.get("response", ""),
        "stats": {
            "total_chunks": len(all_chunks),
            "segments": len(segments),
            "pages": max(c["metadata"]["page"] for c in all_chunks)
        }
    })

@app.get("/documents")
async def list_documents():
    stats = rag.get_collection_stats(COLLECTION_NAME)
    collection = rag.get_or_create_collection(COLLECTION_NAME)
    all_docs = collection.get()
    
    seen_files = {}
    if all_docs['metadatas']:
        for meta in all_docs['metadatas']:
            file_id = meta.get('file_id')
            if file_id and file_id not in seen_files:
                seen_files[file_id] = {
                    "file_id": file_id,
                    "filename": meta.get('filename', 'desconocido'),
                    "chunks": 1
                }
            elif file_id:
                seen_files[file_id]["chunks"] += 1
    
    return JSONResponse(content={
        "total_documents": len(seen_files),
        "total_chunks": stats["total_chunks"],
        "documents": list(seen_files.values())
    })

@app.delete("/delete/{file_id}")
async def delete_document(file_id: str):
    success = rag.delete_document(COLLECTION_NAME, file_id)
    if success:
        return JSONResponse(content={"success": True, "message": f"Documento {file_id} eliminado"})
    else:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

@app.get("/stats")
async def get_stats():
    collection_stats = rag.get_collection_stats(COLLECTION_NAME)
    return JSONResponse(content={
        "collection": collection_stats,
        "ollama_model": OLLAMA_MODEL,
        "upload_folder": UPLOAD_FOLDER
    })

@app.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except:
        ollama_ok = False
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ollama_connected": ollama_ok,
        "chromadb": "active",
        "embeddings_model": "paraphrase-multilingual-MiniLM-L12-v2"
    }

# ============================================================
# ENDPOINTS DE DEPURACIÓN
# ============================================================

@app.get("/debug/chunks/{file_id}")
async def debug_chunks(file_id: str):
    """Muestra los chunks almacenados para un file_id"""
    collection = rag.get_or_create_collection(COLLECTION_NAME)
    results = collection.get(where={"file_id": {"$eq": file_id}})
    
    if not results['ids']:
        return {"error": "No chunks found", "file_id": file_id}
    
    chunks_info = []
    for i in range(min(10, len(results['ids']))):
        chunks_info.append({
            "id": results['ids'][i],
            "page": results['metadatas'][i]['page'],
            "text_preview": results['documents'][i][:200] + "...",
            "metadata": results['metadatas'][i]
        })
    
    return {
        "file_id": file_id,
        "total_chunks": len(results['ids']),
        "sample_chunks": chunks_info
    }

@app.post("/debug/search")
async def debug_search(file_id: str = Form(...), question: str = Form(...)):
    """Muestra qué chunks encuentra y el prompt que se enviaría"""
    relevant_chunks = rag.find_relevant_chunks(
        collection_name=COLLECTION_NAME,
        query=question,
        top_k=5,
        file_id_filter=file_id
    )
    
    if not relevant_chunks:
        return {
            "question": question,
            "found": False,
            "message": "No se encontraron chunks relevantes"
        }
    
    chunks_detail = []
    for chunk in relevant_chunks:
        chunks_detail.append({
            "similarity": chunk["similarity"],
            "page": chunk["metadata"]["page"],
            "text": chunk["text"][:300] + "...",
            "metadata": chunk["metadata"]
        })
    
    context_text = "\n\n".join([
        f"[Página {c['metadata']['page']}]: {c['text']}" 
        for c in relevant_chunks
    ])
    
    prompt = f"""Eres un asistente que SOLO responde basándose en el contexto proporcionado.

CONTEXTO DEL DOCUMENTO (ÚNICA FUENTE DE INFORMACIÓN):
{context_text}

INSTRUCCIONES ESTRICTAS:
1. SOLO usa la información del contexto para responder
2. SI la información no está en el contexto, responde "No encuentro esta información en el texto"

PREGUNTA: {question}

RESPUESTA:"""
    
    return {
        "question": question,
        "chunks_found": len(chunks_detail),
        "chunks": chunks_detail,
        "prompt_to_send": prompt
    }

@app.get("/debug/embedding")
async def debug_embedding(text: str = "Margery Meanwell"):
    embedding = rag.generate_embedding(text)
    return {
        "text": text,
        "embedding_length": len(embedding),
        "embedding_preview": embedding[:5],
        "embedding_stats": {
            "min": min(embedding),
            "max": max(embedding),
            "mean": sum(embedding) / len(embedding)
        }
    }

@app.post("/debug/extract")
async def debug_extract(file: UploadFile = File(...)):
    """Muestra cómo se extrae un PDF sin indexarlo"""
    file_id = str(uuid.uuid4())
    temp_pdf = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
    content = await file.read()
    
    with open(temp_pdf, "wb") as f:
        f.write(content)
    
    try:
        chunks = await extract_pdf_chunks(temp_pdf, file.filename)
        chunks_detail = []
        for i, chunk in enumerate(chunks[:10]):
            chunks_detail.append({
                "chunk_index": i,
                "page": chunk["page"],
                "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "length": len(chunk["text"])
            })
        return {
            "filename": file.filename,
            "total_chunks": len(chunks),
            "sample_chunks": chunks_detail
        }
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

@app.post("/debug/reset")
async def reset_collection():
    """Resetea la colección (borra todos los datos)"""
    success = rag.reset_collection(COLLECTION_NAME)
    if success:
        return {"message": "Colección reseteada correctamente"}
    else:
        return {"error": "No se pudo resetear la colección"}