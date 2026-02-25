import os
import uuid
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import re

class RAGEngine:
    """Motor RAG con ChromaDB y embeddings multilingües"""
    
    def __init__(self, persist_directory: str = "./chroma_data"):
        os.makedirs(persist_directory, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        print(" Cargando modelo de embeddings (multilingüe)...")
        # Modelo robusto para español/inglés con buena tolerancia a ruido OCR
        self.embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("✓ Modelo de embeddings listo")
        
        self.collections = {}
    
    def get_or_create_collection(self, collection_name: str) -> chromadb.Collection:
        try:
            collection = self.chroma_client.get_collection(collection_name)
        except:
            collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return collection
    
    def generate_embedding(self, text: str) -> List[float]:
        return self.embedder.encode(text).tolist()
    
    def add_document_chunks(self, collection_name: str, chunks: List[Dict[str, Any]],
                            file_id: str, filename: str) -> int:
        collection = self.get_or_create_collection(collection_name)
        
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{file_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
            embedding = self.generate_embedding(chunk["text"])
            
            metadata = {
                "file_id": file_id,
                "filename": filename,
                "page": chunk["page"],
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            
            ids.append(chunk_id)
            embeddings.append(embedding)
            metadatas.append(metadata)
            documents.append(chunk["text"])
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
        
        print(f"✓ {len(chunks)} chunks añadidos a '{collection_name}'")
        return len(chunks)
    
    def find_relevant_chunks(self, collection_name: str, query: str,
                             top_k: int = 15, file_id_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        collection = self.get_or_create_collection(collection_name)
        
        query_embedding = self.generate_embedding(query)
        where_filter = {"file_id": {"$eq": file_id_filter}} if file_id_filter else None
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        chunks = []
        if results['ids'][0]:
            for i in range(len(results['ids'][0])):
                chunks.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "similarity": 1 - results['distances'][0][i]
                })
        return chunks
    
    def delete_document(self, collection_name: str, file_id: str) -> bool:
        collection = self.get_or_create_collection(collection_name)
        results = collection.get(where={"file_id": {"$eq": file_id}})
        if results['ids']:
            collection.delete(ids=results['ids'])
            return True
        return False
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        collection = self.get_or_create_collection(collection_name)
        all_docs = collection.get()
        file_ids = set(m.get('file_id') for m in all_docs['metadatas'] if m)
        return {
            "collection": collection_name,
            "total_chunks": len(all_docs['ids']),
            "total_documents": len(file_ids)
        }
    
    def reset_collection(self, collection_name: str) -> bool:
        try:
            self.chroma_client.delete_collection(collection_name)
            return True
        except:
            return False


_rag_engine_instance = None

def get_rag_engine() -> RAGEngine:
    global _rag_engine_instance
    if _rag_engine_instance is None:
        _rag_engine_instance = RAGEngine()
    return _rag_engine_instance