from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
import httpx
import os
from utils import get_current_user

router = APIRouter()

# URL of the collection service
COLLECTION_SERVICE_URL = os.getenv("COLLECTION_SERVICE_URL", "http://collection_service:8000")

async def handle_httpx_error(response):
    """Extracts detailed error messages from HTTPX responses."""
    try:
        error_detail = response.json()
        if isinstance(error_detail, dict) and "detail" in error_detail:
            return error_detail["detail"]
    except Exception:
        return response.text
    return "Unknown error occurred"

@router.get("/")
async def get_collections(user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{COLLECTION_SERVICE_URL}/collections", params={"user_id": user_id})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=await handle_httpx_error(response))
    return response.json()

@router.post("/")
async def create_collection(request: Request, user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    data = await request.json()
    data["user_id"] = user_id
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{COLLECTION_SERVICE_URL}/collections", json=data)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=await handle_httpx_error(response))
    return response.json()

@router.post("/{collection_id}/upload")
async def upload_pdf(collection_id: int, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    file_content = await file.read()
    files = {"file": (file.filename, file_content, file.content_type)}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{COLLECTION_SERVICE_URL}/collections/{collection_id}/upload", files=files)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=await handle_httpx_error(response))
    return response.json()

@router.delete("/{collection_id}/pdfs/{file_id}")
async def delete_pdf(collection_id: int, file_id: str, user: dict = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{COLLECTION_SERVICE_URL}/collections/{collection_id}/pdfs/{file_id}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=await handle_httpx_error(response))
    return response.json()

@router.post("/{collection_id}/scan")
async def scan_collection(collection_id: int, user: dict = Depends(get_current_user)):
    """Forwards a scan request to the collection service"""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{COLLECTION_SERVICE_URL}/collections/{collection_id}/scan")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=await handle_httpx_error(response))
    return response.json()
