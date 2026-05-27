import os
from datetime import timedelta, datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models import Base, User
from schemas import UserCreate, UserLogin  # Zorg dat deze schema’s de nodige velden bevatten
from repository import UserRepository
from auth import AuthManager
from utils import verify_password

app = FastAPI()

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
security = HTTPBearer()

# Initialiseer de AuthManager
auth_manager = AuthManager()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = auth_manager.verify_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    repo = UserRepository(db)
    user = repo.get_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user


@app.post("/register")
def register(user_create: UserCreate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    if repo.get_by_username(user_create.username):
        raise HTTPException(status_code=400, detail="Username already registered")

    # Maak de user aan in de database
    user = repo.create_user(user_create.username, user_create.password)

    # Genereer een access token; we voegen hier ook een "iat" (issued at) toe
    access_token = auth_manager.create_access_token(
        data={"sub": user.username, "user_id": user.id, "iat": int(datetime.utcnow().timestamp())},
        expires_delta=timedelta(minutes=auth_manager.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    created_at = datetime.utcnow().isoformat()

    return {
        "user": {"id": user.id, "username": user.username},
        "token": {"accessToken": access_token, "createdAt": created_at}
    }


@app.post("/login")
def login(user_login: UserLogin, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_username(user_login.username)
    if not user or not verify_password(user_login.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = auth_manager.create_access_token(
        data={"sub": user.username, "user_id": user.id, "iat": int(datetime.utcnow().timestamp())},
        expires_delta=timedelta(minutes=auth_manager.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    created_at = datetime.utcnow().isoformat()

    return {
        "user": {"id": user.id, "username": user.username},
        "token": {"accessToken": access_token, "createdAt": created_at}
    }