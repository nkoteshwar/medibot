"""
Test and comparison script for Hybrid RAG vs Dense-Only RAG,
demonstrating the effect of BM25 keyword search and Cross-Encoder Reranking.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.ingestion import get_vector_store
from backend.rag import rerank_chunks, build_role_filter
from langchain_qdrant import RetrievalMode

TEST_QUERIES = [
    {
        "query": "What is the ICD-10 diagnosis code for STEMI anterior wall and its negotiated rate?",
        "role": "admin",
        "type": "Exact Code & Terminology (ICD-10 I21.0)"
    },
    {
        "query": "IV cannula gauge size and infusion rate for pediatric resuscitation",
        "role": "doctor",
        "type": "Specific Clinical Numbers & Specifications"
    },
    {
        "query": "Calibration error fault code F-05 on DriveFlow IP-200 infusion pump",
        "role": "technician",
        "type": "Exact Equipment Model & Fault Code"
    }
]

def run_hybrid_comparison():
    print("=" * 80)
    print("HYBRID RAG (DENSE + BM25) VS DENSE-ONLY RETRIEVAL & RERANKING BENCHMARK")
    print("=" * 80)
    
    vectorstore = get_vector_store()
    
    for item in TEST_QUERIES:
        q = item["query"]
        role = item["role"]
        q_type = item["type"]
        
        print(f"\n=======================================================")
        print(f"Query: \"{q}\"")
        print(f"Role: {role} | Test Intent: {q_type}")
        print(f"=======================================================")
        
        role_filter = build_role_filter(role)
        
        # 1. Broad Hybrid Retrieval (Top 10)
        hybrid_docs = vectorstore.similarity_search(query=q, k=10, filter=role_filter)
        print(f"\n[1. Initial Hybrid Retrieval (Dense + BM25)] Retrieved: {len(hybrid_docs)} candidates")
        for i, d in enumerate(hybrid_docs[:5], 1):
            src = d.metadata.get("source_document", "Unknown")
            sec = d.metadata.get("section_title", "General")
            excerpt = d.page_content[:120].strip().encode("ascii", errors="replace").decode("ascii")
            print(f"  Candidate #{i}: [{d.metadata.get('collection')}] {src} -> {sec}")
            print(f"    Excerpt: {excerpt}...")

        # 2. Cross-Encoder Reranking
        top_reranked, logs = rerank_chunks(query=q, candidates=hybrid_docs, top_n=3)
        print(f"\n[2. Cross-Encoder Joint Scoring & Reranking (ms-marco-MiniLM-L-6-v2)]")
        for log in logs:
            initial = log["initial_rank"]
            new_r = log["new_rank"]
            shift = "[UP]" if new_r < initial else ("[DOWN]" if new_r > initial else "[SAME]")
            src = log["source_document"].encode("ascii", errors="replace").decode("ascii")
            sec = log["section_title"].encode("ascii", errors="replace").decode("ascii")
            print(f"  Top Pick #{new_r} (was #{initial} {shift}): Score = {log['score']} | {src} ({sec})")

    print("\n" + "=" * 80)
    print("Hybrid Retrieval and Reranking Benchmark Completed Successfully")
    print("=" * 80)

if __name__ == "__main__":
    run_hybrid_comparison()
