from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
import os
from utils import get_current_user

router = APIRouter()
SESSION_SERVICE_URL = os.getenv("SESSION_SERVICE_URL", "http://session_service:8000")

@router.get("/budget")
async def get_budget():
    """Fetches the shared budget from the session_service."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{SESSION_SERVICE_URL}/budget")
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()

@router.post("/")
async def create_session(request: Request, user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    data = await request.json()
    data["user_id"] = user_id
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{SESSION_SERVICE_URL}/sessions", json=data)
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()

@router.get("/{session_id}")
async def get_session(session_id: int, user: dict = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{SESSION_SERVICE_URL}/sessions/{session_id}")
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()

@router.get("/")
async def get_sessions(user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{SESSION_SERVICE_URL}/sessions", params={"user_id": user_id})
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()

@router.get("/{session_id}/chunks")
async def get_session_chunks(session_id: int, user: dict = Depends(get_current_user)):
    """Haalt sessiegegevens + chunked_relevance op uit de session_service."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{SESSION_SERVICE_URL}/sessions/{session_id}/chunks")
    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)
    return response.json()


@router.post("/{session_id}/submit")
async def submit_selected_chunks(session_id: int, request: Request, user: dict = Depends(get_current_user)):
    """Verstuurt de geselecteerde chunks naar de session_service en werkt de sessiestatus bij."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{SESSION_SERVICE_URL}/sessions/{session_id}/submit", json=await request.json())

    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)

    return response.json()


@router.post("/{session_id}/resubmit")
async def resubmit_session(session_id: int, force: bool = False, user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SESSION_SERVICE_URL}/sessions/{session_id}/resubmit",
            params={"user_id": user_id, "force": str(force).lower()},
        )

    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)

    return response.json()


@router.delete("/{session_id}")
async def delete_session(session_id: int, user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{SESSION_SERVICE_URL}/sessions/{session_id}",
            params={"user_id": user_id},
        )

    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)

    return response.json()

@router.get("/{session_id}/result")
async def get_session_result(session_id: int, user: dict = Depends(get_current_user)):
    """Haalt de sessieresultaten op, inclusief de geselecteerde chunks en geëxtraheerde causale relaties."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{SESSION_SERVICE_URL}/sessions/{session_id}/result")

    if response.status_code != 200:
        try:
            error_detail = response.json()
            if isinstance(error_detail, dict) and "detail" in error_detail:
                error_detail = error_detail["detail"]
        except Exception:
            error_detail = response.text
        raise HTTPException(status_code=response.status_code, detail=error_detail)

    return response.json()
