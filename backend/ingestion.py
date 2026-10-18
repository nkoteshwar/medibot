import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from transformers import AutoTokenizer
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from backend.config import (
    DATA_DIR,
    QDRANT_STORAGE_PATH,
    EMBED_MODEL,
    COLLECTION_ACCESS_ROLES
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

COLLECTION_NAME = "medibot_knowledge"
FULL_CACHE_PATH = Path(QDRANT_STORAGE_PATH) / "full_chunks_cache.json"

_shared_client: Optional[QdrantClient] = None
_shared_vector_store: Optional[QdrantVectorStore] = None

def get_embeddings():
    dense_embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )
    sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)
    return dense_embeddings, sparse_embeddings

def get_chunk_type(chunk) -> str:
    """Determine chunk type (table, code, heading, or text) from Docling metadata."""
    if hasattr(chunk, "meta") and hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
        labels = [str(getattr(item, "label", "")).lower() for item in chunk.meta.doc_items]
        if any("table" in l for l in labels):
            return "table"
        if any("code" in l for l in labels):
            return "code"
        if any("header" in l or "title" in l or "heading" in l for l in labels):
            return "heading"
    return "text"

def get_section_title(chunk) -> str:
    """Extract section title or hierarchy from Docling chunk metadata."""
    if hasattr(chunk, "meta") and hasattr(chunk.meta, "headings") and chunk.meta.headings:
        return " > ".join(chunk.meta.headings)
    return "General Section"

def parse_and_chunk_documents() -> List[Document]:
    """
    Parses all documents in mediassist_data using Docling and HybridChunker.
    If full_chunks_cache.json exists, loads directly from cache.
    """
    os.makedirs(QDRANT_STORAGE_PATH, exist_ok=True)
    if FULL_CACHE_PATH.exists():
        logger.info(f"Loading pre-parsed chunks from cache: {FULL_CACHE_PATH}")
        try:
            with open(FULL_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            docs = [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in data]
            logger.info(f"Loaded {len(docs)} documents from cache.")
            return docs
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}. Re-parsing from source documents.")

    logger.info("Initializing Docling DocumentConverter and HybridChunker...")
    converter = DocumentConverter()
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)
    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=128,
        merge_peers=True
    )

    all_docs: List[Document] = []
    
    for col_dir in DATA_DIR.iterdir():
        if not col_dir.is_dir() or col_dir.name in ["db", "__pycache__"]:
            continue
        
        collection_key = col_dir.name.lower()
        if collection_key not in COLLECTION_ACCESS_ROLES:
            continue
            
        access_roles = COLLECTION_ACCESS_ROLES[collection_key]
        files = list(col_dir.glob("*.pdf")) + list(col_dir.glob("*.md"))
        logger.info(f"Processing collection '{collection_key}' ({len(files)} files)...")
        
        for file_path in files:
            doc_name = file_path.name
            logger.info(f"  Parsing {collection_key}/{doc_name} with Docling...")
            
            try:
                res = converter.convert(str(file_path))
                dl_doc = res.document
                chunks = list(chunker.chunk(dl_doc=dl_doc))
                logger.info(f"    Generated {len(chunks)} chunks for {doc_name}")
                
                for idx, c in enumerate(chunks):
                    try:
                        text_content = chunker.contextualize(chunk=c)
                    except Exception:
                        try:
                            text_content = chunker.serialize(chunk=c)
                        except Exception:
                            text_content = c.text
                            
                    sec_title = get_section_title(c)
                    c_type = get_chunk_type(c)
                    
                    if sec_title and sec_title not in text_content[:150]:
                        text_content = f"[{sec_title}]\n{text_content}"
                        
                    doc_meta = {
                        "source_document": doc_name,
                        "collection": collection_key,
                        "access_roles": access_roles,
                        "section_title": sec_title,
                        "chunk_type": c_type,
                        "chunk_id": f"{doc_name}_chunk_{idx}"
                    }
                    
                    all_docs.append(Document(
                        page_content=text_content,
                        metadata=doc_meta
                    ))
            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}")

    # Save full cache to disk
    try:
        with open(FULL_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump([
                {
                    "page_content": d.page_content,
                    "metadata": d.metadata
                } for d in all_docs
            ], f, indent=2)
        logger.info(f"Cached all {len(all_docs)} parsed chunks to {FULL_CACHE_PATH}")
    except Exception as e:
        logger.warning(f"Could not write full cache: {e}")

    logger.info(f"Total documents prepared for vector indexing: {len(all_docs)}")
    return all_docs

def get_shared_client() -> QdrantClient:
    global _shared_client
    if _shared_client is None:
        os.makedirs(QDRANT_STORAGE_PATH, exist_ok=True)
        _shared_client = QdrantClient(path=QDRANT_STORAGE_PATH)
    return _shared_client

def build_vector_store(force_rebuild: bool = False) -> QdrantVectorStore:
    """Builds or loads the persistent Hybrid Qdrant Vector Store."""
    global _shared_vector_store
    dense_embeddings, sparse_embeddings = get_embeddings()
    client = get_shared_client()

    try:
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION_NAME in collections:
            count = client.count(COLLECTION_NAME).count
            if count > 0 and not force_rebuild:
                logger.info(f"Loaded existing Qdrant collection '{COLLECTION_NAME}' with {count} points.")
                _shared_vector_store = QdrantVectorStore(
                    client=client,
                    collection_name=COLLECTION_NAME,
                    embedding=dense_embeddings,
                    sparse_embedding=sparse_embeddings,
                    retrieval_mode=RetrievalMode.HYBRID
                )
                return _shared_vector_store
            elif force_rebuild:
                logger.info(f"Force rebuild: deleting existing collection '{COLLECTION_NAME}'...")
                client.delete_collection(COLLECTION_NAME)
    except Exception as e:
        logger.warning(f"Collection check warning: {e}")

    docs = parse_and_chunk_documents()
    logger.info(f"Indexing {len(docs)} documents into Qdrant collection '{COLLECTION_NAME}'...")

    # Create collection with hybrid configuration
    _shared_vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=dense_embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID
    )
    
    # Add documents in batches
    batch_size = 50
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        _shared_vector_store.add_documents(batch)
        logger.info(f"  Indexed batch {i//batch_size + 1} / {(len(docs)-1)//batch_size + 1} ({len(batch)} chunks)")

    count = client.count(COLLECTION_NAME).count
    logger.info(f"Indexed {count} points into Qdrant collection '{COLLECTION_NAME}'.")
    return _shared_vector_store

def get_vector_store() -> QdrantVectorStore:
    """Returns an initialized vector store handle using shared client."""
    global _shared_vector_store
    if _shared_vector_store is not None:
        return _shared_vector_store
    return build_vector_store(force_rebuild=False)

if __name__ == "__main__":
    build_vector_store(force_rebuild=True)
