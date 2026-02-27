
import os
import uuid
import httpx
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
from .pdf_utils import clean_ocr_text, ocr_image, extract_pdf_chunks
from .summarize_utils import summarize_segments
from .app import count_tokens, get_rag_engine, generate_with_context

app = FastAPI(title="PDF Summarizer RAG v2", version="2.1")

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/app/uploads")  
COLLECTION_NAME = "pdf_documents"

rag = get_rag_engine()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

_processing_summaries: Dict[str, asyncio.Future] = {}

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def root():
	return {
		"message": "PDF Summarizer API with RAG v2.1",
		"ollama_model": OLLAMA_MODEL,
		"endpoints": [
			"/upload - Upload PDF",
			"/ask - Ask questions",
			"/summarize/{file_id} - Generate summary",
			"/documents - List documents",
			"/extract-full/{file_id} - Get complete extracted text",  
			"/delete/{file_id} - Delete document",
			"/stats - Statistics",
			"/debug/chunks/{file_id} - View chunks",
			"/debug/search - Test search",
			"/debug/embedding - Test embeddings",
			"/debug/extract - View extraction"
		]
	}

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
	if not file.filename.endswith('.pdf'):
		raise HTTPException(status_code=400, detail="Only PDF files are accepted")
	file_id = str(uuid.uuid4())
	temp_pdf = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
	content = await file.read()
	with open(temp_pdf, "wb") as f:
		f.write(content)
	try:
		chunks = await extract_pdf_chunks(temp_pdf, file.filename)
		if not chunks:
			raise HTTPException(status_code=400, detail="Could not extract text from PDF")
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
			"message": "PDF processed and indexed successfully",
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
		raise HTTPException(status_code=400, detail="Question cannot be empty")
	print(f" Question: {question}")
	print(f" File ID: {file_id}")
	relevant_chunks = rag.find_relevant_chunks(
		collection_name=COLLECTION_NAME,
		query=question,
		top_k=50,
		file_id_filter=file_id
	)
	if not relevant_chunks:
		return JSONResponse(content={
			"question": question,
			"answer": "I couldn't find relevant information in the document to answer this question.",
			"sources": []
		})
	answer = await generate_with_context(question, relevant_chunks)
	if isinstance(answer, str) and answer.startswith("Error"):
		raise HTTPException(status_code=502, detail=answer)
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
	global _processing_summaries
	if file_id in _processing_summaries:
		return await _processing_summaries[file_id]
	loop = asyncio.get_event_loop()
	future = loop.create_future()
	_processing_summaries[file_id] = future
	try:
		print(f" Generating summary for: {file_id}")
		all_chunks = rag.find_relevant_chunks(
			collection_name=COLLECTION_NAME,
			query="",  
			top_k=100,
			file_id_filter=file_id
		)
		if not all_chunks:
			raise HTTPException(status_code=404, detail="Document not found")
		all_chunks.sort(key=lambda x: x["metadata"]["page"])
		segments: List[str] = []
		current_segment: List[str] = []
		current_tokens = 0
		MAX_SEGMENT_TOKENS = 500
		for chunk in all_chunks:
			tok = count_tokens(chunk["text"])
			if current_tokens + tok > MAX_SEGMENT_TOKENS and current_segment:
				segments.append(" ".join(current_segment))
				current_segment = [chunk["text"]]
				current_tokens = tok
			else:
				current_segment.append(chunk["text"])
				current_tokens += tok
		if current_segment:
			segments.append(" ".join(current_segment))
		filename = all_chunks[0]["metadata"].get("filename", "unknown") if all_chunks else "unknown"
		summaries, final_summary = await summarize_segments(
			segments,
			OLLAMA_URL,
			OLLAMA_MODEL,
			count_tokens,
			filename,
			file_id,
			UPLOAD_FOLDER
		)
		response = JSONResponse(
			content={
				"file_id": file_id,
				"filename": filename,
				"summary": final_summary,
				"stats": {
					"total_chunks": len(all_chunks),
					"segments": len(segments),
					"pages": max(c["metadata"]["page"] for c in all_chunks),
				},
			}
		)
		if not future.done():
			future.set_result(response)
		return response
	finally:
		_processing_summaries.pop(file_id, None)

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
					"filename": meta.get('filename', 'unknown'),
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
		return JSONResponse(content={"success": True, "message": f"Document {file_id} deleted"})
	else:
		raise HTTPException(status_code=404, detail="Document not found")

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
# DEBUG ENDPOINTS
# ============================================================

@app.get("/debug/chunks/{file_id}")
async def debug_chunks(file_id: str):
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
			"message": "No relevant chunks found"
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
		f"[Page {c['metadata']['page']}]: {c['text']}" 
		for c in relevant_chunks
	])
	prompt = f"""You are an assistant that ONLY responds based on the provided context.\n\nDOCUMENT CONTEXT (ONLY SOURCE OF INFORMATION):\n{context_text}\n\nSTRICT INSTRUCTIONS:\n1. ONLY use the context information to respond\n2. IF the information is not in the context, respond with \"I couldn't find this information in the text\"\n\nQUESTION: {question}\n\nANSWER:"""
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
	success = rag.reset_collection(COLLECTION_NAME)
	if success:
		return {"message": "Collection reset successfully"}
	else:
		return {"error": "Could not reset collection"}

@app.get("/extract-full/{file_id}")
async def extract_full_text(file_id: str):
	try:
		import os, json
		summary_cache_dir = os.path.join(UPLOAD_FOLDER, "_summary_cache")
		os.makedirs(summary_cache_dir, exist_ok=True)
		cache_path = os.path.join(summary_cache_dir, f"{file_id}_summaries.json")
		if os.path.exists(cache_path):
			with open(cache_path, "r", encoding="utf-8") as f:
				cache_data = json.load(f)
			summaries = cache_data.get("summaries", [])
			filename = cache_data.get("filename", "unknown")
		else:
			summaries = []
			filename = "unknown"
		if not summaries:
			return JSONResponse(
				status_code=404,
				content={"detail": "No summaries found for this document. Please generate a summary first."}
			)
		full_text = "\n\n".join([
			f"[Summary {i+1}]\n{s.strip()}" for i, s in enumerate(summaries)
		])
		return JSONResponse(content={
			"file_id": file_id,
			"filename": filename,
			"full_text": full_text,
			"stats": {
				"total_summaries": len(summaries)
			}
		})
	except Exception as e:
		print(f"Error retrieving concatenated summaries: {e}")
		return JSONResponse(
			status_code=500,
			content={"detail": f"Internal server error: {str(e)}"}
		)
