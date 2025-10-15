# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.settings import settings
from app.api.routes.issue_views import router as issue_router
from app.api.routes.repository_views import router as repo_router
from app.api.routes.cache_views import router as cache_router
from app.api.routes.chatbot_views import router as chatbot_router

from fastapi.staticfiles import StaticFiles
import uuid

app = FastAPI(title="AnalyticsTool API", version="1.0.0")

# Session Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=False,  # Set True in production
    session_cookie="sessionid"
)

# CORS Middleware
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://frontend:80",
    "http://localhost:80",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# for devolopers
# # 🔥 Session ID middleware (her istekte print eder)
# @app.middleware("http")
# async def log_session_id(request: Request, call_next):
#     session_id = request.cookies.get("sessionid") or str(uuid.uuid4())
#     print(f"[SESSION] ID: {session_id} | Path: {request.url.path}")
#
#     response = await call_next(request)
#     response.set_cookie(key="sessionid", value=session_id)
#     return response


# API routes
app.include_router(issue_router, prefix="/api/issues", tags=["Issues"])
app.include_router(repo_router, prefix="/api/repositories", tags=["Repositories"])
app.include_router(cache_router, prefix="/api/cache", tags=["Cache"])
app.include_router(chatbot_router, prefix="/api/chatbot", tags=["Chatbot"])
# Static files
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")
