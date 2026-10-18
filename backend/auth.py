import jwt
import datetime
from typing import Optional
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import JWT_SECRET, ROLE_COLLECTION_ACCESS, ROLE_METADATA

security = HTTPBearer(auto_error=False)

DEMO_USERS = {
    "dr.mehta": {
        "username": "dr.mehta",
        "name": "Dr. Rajesh Mehta",
        "role": "doctor",
        "department": "Clinical Medicine",
        "passwords": ["medibot123", "doctor123"]
    },
    "nurse.priya": {
        "username": "nurse.priya",
        "name": "Nurse Priya Sharma",
        "role": "nurse",
        "department": "Nursing & Patient Care",
        "passwords": ["medibot123", "nurse123"]
    },
    "billing.ravi": {
        "username": "billing.ravi",
        "name": "Ravi Kumar",
        "role": "billing_executive",
        "department": "Billing & Insurance",
        "passwords": ["medibot123", "billing123"]
    },
    "tech.anand": {
        "username": "tech.anand",
        "name": "Anand Verma",
        "role": "technician",
        "department": "Biomedical Equipment",
        "passwords": ["medibot123", "tech123"]
    },
    "admin.sys": {
        "username": "admin.sys",
        "name": "Systems Administrator",
        "role": "admin",
        "department": "Executive / IT Operations",
        "passwords": ["medibot123", "admin123"]
    }
}

def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = DEMO_USERS.get(username.strip().lower())
    if not user:
        return None
    if password.strip() in user["passwords"]:
        return {
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "department": user["department"],
            "accessible_collections": ROLE_COLLECTION_ACCESS.get(user["role"], ["general"])
        }
    return None

def create_access_token(user_data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    payload = user_data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    payload.update({"exp": expire})
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[dict]:
    if not credentials:
        return None
    token = credentials.credentials
    return decode_access_token(token)
