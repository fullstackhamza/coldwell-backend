import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ..auth_utils import (
    create_access_token,
    get_current_user_id,
    hash_password,
    verify_password,
)
from ..database import get_db
from ..models.user import Token, UserCreate, UserLogin, UserPublic
from ..rate_limit import rate_limit_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _doc_to_public(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "full_name": doc["full_name"],
        "email": doc["email"],
        "role": doc.get("role", "customer"),
    }


@router.post(
    "/signup",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
def signup(payload: UserCreate, db: Database = Depends(get_db)):
    if db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_id = secrets.token_hex(12)
    doc = {
        "id": user_id,
        "full_name": payload.full_name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        # New accounts are always plain customers — admins are promoted
        # separately via `python -m app.create_admin`, never self-assigned.
        "role": "customer",
    }
    db.users.insert_one(doc)
    token = create_access_token(user_id)
    return Token(access_token=token, user=UserPublic(**_doc_to_public(doc)))


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit_auth)])
def login(payload: UserLogin, db: Database = Depends(get_db)):
    doc = db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(doc["id"])
    return Token(access_token=token, user=UserPublic(**_doc_to_public(doc)))


@router.get("/me", response_model=UserPublic)
def me(
    user_id: str = Depends(get_current_user_id), db: Database = Depends(get_db)
):
    doc = db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return UserPublic(**_doc_to_public(doc))
