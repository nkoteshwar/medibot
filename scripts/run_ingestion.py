"""
Convenience script to run document ingestion and build the Hybrid Qdrant Vector Store.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.ingestion import build_vector_store

if __name__ == "__main__":
    print("=== MediBot Document Ingestion Pipeline ===")
    print("Parsing documents with Docling & HybridChunker...")
    vectorstore = build_vector_store(force_rebuild=True)
    print("=== Document Ingestion Completed Successfully ===")
