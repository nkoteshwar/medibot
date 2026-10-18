"""
Test script for MediBot SQL RAG Component.
Validates the sql_rag_chain plain Python function across multiple analytical questions.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.db import sql_rag_chain, run_sql_rag_with_metadata

TEST_QUESTIONS = [
    "How many billing claims are currently pending?",
    "What is the total claimed amount across all claims?",
    "Which equipment category has the highest number of maintenance tickets?",
    "How many maintenance tickets are currently in progress versus resolved?",
    "Which department has submitted the most billing claims?",
    "What is the average claimed amount for cardiology department claims?"
]

def run_tests():
    print("=" * 70)
    print("MEDIBOT SQL RAG COMPONENT EVALUATION")
    print("=" * 70)
    
    for idx, q in enumerate(TEST_QUESTIONS, 1):
        print(f"\n--- [Question {idx}] {q} ---")
        try:
            res = run_sql_rag_with_metadata(q)
            print(f"Generated SQL: {res['sql']}")
            print(f"Raw Result   : {res['result']}")
            # Safe print for Windows terminal
            answer_clean = res['answer'].encode('ascii', errors='replace').decode('ascii')
            print(f"Final Answer : {answer_clean}")
        except Exception as e:
            print(f"FAILED: {e}")
            
    print("\n" + "=" * 70)
    print("SQL RAG Test Run Complete")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
