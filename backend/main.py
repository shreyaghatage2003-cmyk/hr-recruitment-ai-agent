from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.database.db import init_db
from backend.api.routes import candidates, interview, screening, scheduling, dashboard
from backend.api.websockets.interview_ws import interview_websocket
from backend.api.websockets.chatbot_ws import chatbot_websocket
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="HR Recruitment Agent System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(candidates.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(screening.router, prefix="/api")
app.include_router(scheduling.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


# WebSocket endpoints
@app.websocket("/ws/interview/{candidate_id}")
async def ws_interview(websocket: WebSocket, candidate_id: int):
    await interview_websocket(websocket, candidate_id)


@app.websocket("/ws/chatbot/{session_id}")
async def ws_chatbot(websocket: WebSocket, session_id: str):
    await chatbot_websocket(websocket, session_id)


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
