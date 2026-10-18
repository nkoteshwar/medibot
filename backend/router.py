import re
import logging
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from backend.config import GROQ_MODEL, GROQ_API_KEY, ANALYTICAL_ROLES, ROLE_COLLECTION_ACCESS, ROLE_METADATA
from backend.db import run_sql_rag_with_metadata
from backend.rag import run_hybrid_rag

logger = logging.getLogger(__name__)

def is_analytical_question(question: str) -> bool:
    """
    Determines if the question requires SQL RAG over relational tables (claims / maintenance_tickets)
    vs document retrieval (protocols, formularies, handbooks, etc.).
    """
    q_lower = question.lower()
    
    # Direct heuristics for relational metrics
    sql_patterns = [
        r"\bhow many (claims|tickets|patients|records)\b",
        r"\btotal (claimed|approved)? ?amount\b",
        r"\baverage (claimed|approved)? ?amount\b",
        r"\bcount of\b",
        r"\bmost (open|closed|pending)? ?(tickets|claims)\b",
        r"\bwhich equipment (category|campus|name) has the most\b",
        r"\bclaims? (pending|approved|rejected|escalated|submitted)\b",
        r"\bmaintenance tickets?\b",
        r"\btickets? by (status|category|campus|issue)\b",
        r"\bnumber of claims\b",
        r"\bnumber of tickets\b",
        r"\bhighest claimed\b",
        r"\blowest claimed\b"
    ]
    
    for pat in sql_patterns:
        if re.search(pat, q_lower):
            logger.info(f"[Router] Heuristic matched analytical query pattern: '{pat}'")
            return True
            
    # If ambiguous, use LLM classifier
    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            temperature=0,
            api_key=GROQ_API_KEY,
            reasoning_format="parsed"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intent classifier for MediAssist Health Network.
Classify whether the user's question is asking for:
'SQL' - quantitative/aggregate queries requiring database calculation over 'claims' or 'maintenance_tickets' tables (e.g. counts, sums, averages, ticket statuses, top categories).
'DOCUMENT' - informational, clinical, protocol, policy, drug dosing, billing guide, or manual inquiries requiring document retrieval.

Respond with ONLY the single word 'SQL' or 'DOCUMENT'."""),
            ("human", "{question}")
        ])
        chain = prompt | llm
        decision = chain.invoke({"question": question}).content.strip().upper()
        logger.info(f"[Router] LLM classifier determined query type: {decision}")
        return "SQL" in decision
    except Exception as e:
        logger.warning(f"[Router] Classifier fallback error: {e}")
        return False

def route_and_execute(question: str, role: str) -> Dict[str, Any]:
    """
    Main routing logic as specified in the assignment flowchart:
    1. Check if analytical / numbers question
    2. If yes:
       - If role permitted (billing_executive, admin) -> Execute SQL RAG
       - If role not permitted -> Return RBAC Refusal
    3. If no:
       - Execute Hybrid RAG + RBAC filter + Reranking -> Return Answer + Sources
    """
    role_norm = role.lower().strip()
    is_analytical = is_analytical_question(question)
    
    if is_analytical:
        logger.info(f"[Router] Routing to SQL RAG path for role '{role_norm}'")
        
        # Check RBAC authorization for SQL RAG
        if role_norm not in ANALYTICAL_ROLES:
            dept = ROLE_METADATA.get(role_norm, {}).get("department", role_norm)
            accessible_cols = ", ".join(f"'{c}'" for c in ROLE_COLLECTION_ACCESS.get(role_norm, ["general"]))
            refusal = (
                f"🔒 **Access Control Refusal (RBAC Policy):**\n\n"
                f"As a **{role_norm.replace('_', ' ').title()}** ({dept}), you do not have permission to execute operational SQL analytics or query the internal financial/maintenance databases.\n\n"
                f"• **Authorized Roles for Database Analytics:** Billing Executives (`billing_executive`) and System Administrators (`admin`).\n"
                f"• **Your Permitted Document Collections:** {accessible_cols}."
            )
            return {
                "answer": refusal,
                "sources": [],
                "retrieval_type": "sql_rag",
                "role": role_norm,
                "access_blocked": True
            }
            
        # Role is authorized: execute SQL RAG
        res = run_sql_rag_with_metadata(question)
        return {
            "answer": res["answer"],
            "sources": res["sources"],
            "retrieval_type": "sql_rag",
            "role": role_norm,
            "sql_query": res.get("sql"),
            "access_blocked": False
        }
        
    else:
        logger.info(f"[Router] Routing to Hybrid RAG path for role '{role_norm}'")
        rag_res = run_hybrid_rag(query=question, role=role_norm)
        return rag_res
