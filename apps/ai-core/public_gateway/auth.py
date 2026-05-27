from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
import os
from utils import get_current_user

router = APIRouter()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")

@router.post("/register")
async def register(request: Request):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{AUTH_SERVICE_URL}/register", json=data)
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()

@router.post("/login")
async def login(request: Request):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{AUTH_SERVICE_URL}/login", json=data)
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()

@router.get("/profile")
async def profile(user: dict = Depends(get_current_user)):
    return {
        "id": user.get('user_id'),
        "username": user.get('sub'),
    }
