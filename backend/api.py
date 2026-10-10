

"""FastAPI backend for the database chatbot."""

import os
import uuid
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()  # reads backend/.env (GOOGLE_API_KEY, ...)

from utils import (  # noqa: E402  (must come after load_dotenv)
    build_graph,
    fetch_table_data,
    get_all_tables,
    get_llm,
    process_chat_query,
    setup_database,
)

app = FastAPI(title="DB Chatbot API", version="2.0.0")

# Allowed browser origins (comma separated). Defaults to the Vite dev server.
origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

setup_database()

# The agent is created lazily so the server still starts (and /health explains the
# problem) when the API key is missing.
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(get_llm())
    return _graph


class ChatRequest(BaseModel):
    input_message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": bool(os.getenv("GOOGLE_API_KEY"))}


@app.get("/tables")
def list_tables():
    return {"status": "success", "tables": get_all_tables()}


@app.get("/tables/data/{table_name}")
def table_data(table_name: str):
    try:
        return {"status": "success", "data": fetch_table_data(table_name)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/chat_query", response_model=ChatResponse)
def chat_query(request: ChatRequest):
    message = request.input_message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Please type a question.")

    session_id = request.session_id or str(uuid.uuid4())
    try:
        answer = process_chat_query(get_graph(), message, session_id)
    except RuntimeError as e:  # e.g. missing API key
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            raise HTTPException(
                status_code=429,
                detail="The free Gemini rate limit was hit. Wait a minute and try again.",
            )
        raise HTTPException(status_code=500, detail=f"Chat processing error: {msg}")

    return ChatResponse(answer=answer or "I couldn't find an answer to that.", session_id=session_id)


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
