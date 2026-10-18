import os
import re
import sqlite3
from typing import Dict, Any, Tuple
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from backend.config import GROQ_MODEL, GROQ_API_KEY, DB_PATH

# Initialize database utility
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

def get_llm():
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0,
        api_key=GROQ_API_KEY,
        reasoning_format="parsed"
    )

def clean_sql(raw: str) -> str:
    """
    Clean the raw LLM output to extract only the SQL statement before executing it.
    Strips markdown fences, preamble/postamble, and comments.
    """
    cleaned = raw.strip()
    # Strip markdown code blocks
    cleaned = re.sub(r"```(?:sql)?", "", cleaned, flags=re.IGNORECASE).strip("`").strip()
    
    # Strip common prefixes like 'SQLQuery:' or 'SQL:' or 'Query:'
    for prefix in ["SQLQuery:", "SQL Query:", "SQL:", "Query:"]:
        if prefix in cleaned:
            cleaned = cleaned.split(prefix)[-1].strip()
            
    # If there is a semicolon, take everything up to the first semicolon
    if ";" in cleaned:
        cleaned = cleaned[:cleaned.index(";") + 1].strip()
    else:
        cleaned = cleaned + ";"
        
    return cleaned

SYSTEM_SQL_GEN_PROMPT = """You are an expert SQLite analyst for MediAssist Health Network.
Your task is to write a SQLite query to answer the user's analytical question based on the schema below.

Database Schema:
{schema}

Guidelines:
- Return ONLY the executable SQL query.
- Do NOT include any explanations, markdown code fences, or pleasantries.
- For status columns, check standard lowercase values like 'pending', 'approved', 'rejected', 'in_progress', 'resolved'.
- For aggregate counts or sums, use appropriate SQL functions (COUNT, SUM, AVG, MAX, MIN).
- Only read queries (SELECT) are permitted.
"""

SYSTEM_ANSWER_PROMPT = """You are MediAssist Health Network's operational analytics assistant.
Given the original question, the generated SQL query, and the database execution results, provide a clear, concise, professional natural language answer.
Highlight key numbers, metrics, departments, or statuses directly and accurately.
"""

def sql_rag_chain(question: str) -> str:
    """
    Plain Python function implementing the three explicit steps required:
    1. Translate the natural language question into a SQL query using an LLM
    2. Clean the raw LLM output to extract only the SQL statement before executing it
    3. Execute the SQL against the database, then pass the result back to the LLM to produce a natural language answer
    """
    llm = get_llm()
    schema = db.get_table_info()
    
    # Step 1: Translate question to SQL
    prompt_gen = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_SQL_GEN_PROMPT),
        ("human", "Question: {question}")
    ])
    chain_gen = prompt_gen | llm
    raw_sql = chain_gen.invoke({"schema": schema, "question": question}).content
    
    # Step 2: Clean the raw LLM output
    sql = clean_sql(raw_sql)
    print(f"[SQL RAG] Cleaned SQL: {sql}")
    
    # Step 3: Execute SQL against database and synthesize answer
    try:
        db_result = db.run(sql)
    except Exception as e:
        print(f"[SQL RAG Error executing SQL] {sql} -> {e}")
        db_result = f"Error executing query: {str(e)}"
        
    prompt_ans = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_ANSWER_PROMPT),
        ("human", "Question: {question}\nExecuted SQL: {sql}\nDatabase Result: {result}\n\nAnswer:")
    ])
    chain_ans = prompt_ans | llm
    answer_res = chain_ans.invoke({"question": question, "sql": sql, "result": db_result})
    return answer_res.content

def run_sql_rag_with_metadata(question: str) -> Dict[str, Any]:
    """Helper to return answer along with executed query and sources."""
    llm = get_llm()
    schema = db.get_table_info()
    
    prompt_gen = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_SQL_GEN_PROMPT),
        ("human", "Question: {question}")
    ])
    chain_gen = prompt_gen | llm
    raw_sql = chain_gen.invoke({"schema": schema, "question": question}).content
    sql = clean_sql(raw_sql)
    
    try:
        db_result = db.run(sql)
    except Exception as e:
        db_result = f"Error: {e}"
        
    prompt_ans = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_ANSWER_PROMPT),
        ("human", "Question: {question}\nExecuted SQL: {sql}\nDatabase Result: {result}\n\nAnswer:")
    ])
    chain_ans = prompt_ans | llm
    answer = chain_ans.invoke({"question": question, "sql": sql, "result": db_result}).content
    
    return {
        "answer": answer,
        "sql": sql,
        "result": str(db_result),
        "sources": [
            {
                "source_document": "mediassist.db",
                "section_title": f"SQL Query: {sql}",
                "collection": "relational_database"
            }
        ]
    }
