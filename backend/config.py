import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

# Model & Provider configs
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
JWT_SECRET = os.getenv("JWT_SECRET", "medibot-secret-key-super-secure-2026")

# Paths
QDRANT_STORAGE_PATH = str(BASE_DIR / "qdrant_storage")
DATA_DIR = PROJECT_DIR / "mediassist_data"
DB_PATH = str(DATA_DIR / "db" / "mediassist.db")

# User Roles & Access Matrix
# Roles: doctor, nurse, billing_executive, technician, admin
ROLE_COLLECTION_ACCESS = {
    "doctor": ["clinical", "nursing", "general"],
    "nurse": ["nursing", "general"],
    "billing_executive": ["billing", "general"],
    "technician": ["equipment", "general"],
    "admin": ["general", "clinical", "nursing", "billing", "equipment"]
}

COLLECTION_ACCESS_ROLES = {
    "general": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical": ["doctor", "admin"],
    "nursing": ["nurse", "doctor", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"]
}

COLLECTION_NAMES = ["general", "clinical", "nursing", "billing", "equipment"]

# Roles authorized to query SQL analytical database (claims & maintenance_tickets)
ANALYTICAL_ROLES = ["billing_executive", "admin"]

ROLE_METADATA = {
    "doctor": {
        "title": "Dr. (Physician / Clinical Specialist)",
        "department": "Clinical Medicine",
        "description": "Authorized for clinical treatment protocols, drug formulary, diagnostic guidelines, nursing procedures, and general policies."
    },
    "nurse": {
        "title": "Staff Nurse / ICU Care Specialist",
        "department": "Nursing & Patient Care",
        "description": "Authorized for nursing procedures, infection control, patient care protocols, and general policies."
    },
    "billing_executive": {
        "title": "Billing & Claims Executive",
        "department": "Billing & Insurance",
        "description": "Authorized for insurance billing codes, claim guides, general policies, and claims database analytics."
    },
    "technician": {
        "title": "Biomedical Equipment Technician",
        "department": "Biomedical Engineering",
        "description": "Authorized for equipment operation & maintenance manuals, calibration guides, and general policies."
    },
    "admin": {
        "title": "Hospital Network Administrator",
        "department": "Executive / IT Operations",
        "description": "Full access to all document collections and operational database analytics."
    }
}
