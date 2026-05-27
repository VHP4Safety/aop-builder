from fastapi import FastAPI
from auth import router as auth_router
from collection import router as collection_router
from session import router as session_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Public Gateway")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://crebuilder.vhp4safety.nl",
    "https://crebuilder.vhp4safety.nl"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(collection_router, prefix="/collections", tags=["collections"])
app.include_router(session_router, prefix="/sessions", tags=["cer_sessions"])
