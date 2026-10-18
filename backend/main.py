import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import (
    ROLE_COLLECTION_ACCESS,
    ROLE_METADATA,
    COLLECTION_ACCESS_ROLES,
    ANALYTICAL_ROLES
)
from backend.auth import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    get_current_user,
    DEMO_USERS
)
from backend.router import route_and_execute
from backend.ingestion import get_vector_store, build_vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MediBot Backend API",
    description="Advanced RAG with Hybrid Search, Cross-Encoder Reranking, SQL RAG, and Role-Based Access Control",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request & Response Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    username: str
    name: str
    role: str
    department: str
    accessible_collections: List[str]

class ChatRequest(BaseModel):
    question: str = Field(..., example="What is the IV infusion protocol for pediatric patients?")
    role: Optional[str] = Field(None, example="nurse")

class SourceCitation(BaseModel):
    source_document: str
    section_title: str
    collection: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    retrieval_type: str  # "hybrid_rag" or "sql_rag"
    role: str
    sql_query: Optional[str] = None
    access_blocked: Optional[bool] = False
    rerank_logs: Optional[List[Dict[str, Any]]] = None

# Endpoints

@app.get("/health")
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "MediBot API",
        "version": "1.0.0",
        "models": {
            "llm": "Groq / openai/gpt-oss-20b",
            "dense_embeddings": "sentence-transformers/all-MiniLM-L6-v2",
            "sparse_embeddings": "Qdrant/bm25",
            "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2"
        }
    }

@app.get("/demo-users")
def get_demo_users():
    """Returns available demo accounts for the Next.js frontend login screen."""
    users_info = []
    for username, data in DEMO_USERS.items():
        role = data["role"]
        users_info.append({
            "username": username,
            "name": data["name"],
            "role": role,
            "department": data["department"],
            "accessible_collections": ROLE_COLLECTION_ACCESS.get(role, ["general"]),
            "is_analytical": role in ANALYTICAL_ROLES,
            "sample_password": data["passwords"][0]
        })
    return {"demo_users": users_info}

@app.post("/login", response_model=LoginResponse)
def login(creds: LoginRequest):
    """
    Accepts username and password, validates against MediAssist directory,
    and returns a role-tagged session token.
    """
    user = authenticate_user(creds.username, creds.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Use one of the demo accounts provided."
        )
    
    token = create_access_token(user)
    return LoginResponse(
        token=token,
        username=user["username"],
        name=user["name"],
        role=user["role"],
        department=user["department"],
        accessible_collections=user["accessible_collections"]
    )

@app.get("/collections/{role}")
def get_role_collections(role: str):
    """
    Returns the list of document collections accessible to the given role.
    """
    role_norm = role.lower().strip()
    if role_norm not in ROLE_COLLECTION_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role}' not recognized in MediAssist directory."
        )
    return {
        "role": role_norm,
        "department": ROLE_METADATA.get(role_norm, {}).get("department", "Unknown"),
        "accessible_collections": ROLE_COLLECTION_ACCESS[role_norm],
        "all_collections": list(COLLECTION_ACCESS_ROLES.keys()),
        "can_query_sql": role_norm in ANALYTICAL_ROLES
    }

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    req: ChatRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Main RAG endpoint. Accepts question and role (from token or request body),
    applies RBAC filter, routes to hybrid+rerank RAG or SQL RAG,
    and returns answer + sources + retrieval_type + role.
    """
    # Determine authenticated role
    if current_user and "role" in current_user:
        active_role = current_user["role"]
    elif req.role:
        active_role = req.role.lower().strip()
    else:
        # Default fallback
        active_role = "general_staff"

    if active_role not in ROLE_COLLECTION_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or missing role '{active_role}'. Please login with a valid role."
        )
        
    logger.info(f"[/chat] Question: '{req.question}' | Active Role: '{active_role}'")
    
    # Route through the intelligent routing pipeline
    result = route_and_execute(question=req.question, role=active_role)
    
    sources = [
        SourceCitation(
            source_document=s.get("source_document", "Unknown"),
            section_title=s.get("section_title", "General"),
            collection=s.get("collection", "general")
        )
        for s in result.get("sources", [])
    ]
    
    return ChatResponse(
        answer=result.get("answer", "No answer generated."),
        sources=sources,
        retrieval_type=result.get("retrieval_type", "hybrid_rag"),
        role=active_role,
        sql_query=result.get("sql_query"),
        access_blocked=result.get("access_blocked", False),
        rerank_logs=result.get("rerank_logs", [])
    )

@app.post("/admin/reindex")
def trigger_reindex(current_user: Optional[dict] = Depends(get_current_user)):
    """Admin endpoint to re-run ingestion."""
    if current_user and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators may trigger document re-indexing."
        )
    logger.info("Admin triggered vector store reindexing...")
    vs = build_vector_store(force_rebuild=True)
    return {"status": "reindexed", "message": "Document ingestion and indexing completed."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
