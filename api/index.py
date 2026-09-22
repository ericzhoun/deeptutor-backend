"""DeepTutor course backend — FastAPI (ASGI) for Vercel.

A serverless slice of the DeepTutor idea (HKUDS/DeepTutor): RAG-grounded
tutoring, quiz generation, and concept explanation over the Backend System
Design course. The full DeepTutor app (PocketBase, WebSockets, FAISS, agent
sandbox) needs a long-running host — see README for the Docker path.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from kb import CourseKB

HERE = Path(__file__).resolve().parent
KB = CourseKB(HERE / "course.md")

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4.6")
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://olivistart.com,https://ericzhoun.github.io,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",") if o.strip()
]

app = FastAPI(title="DeepTutor Course Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = (
    "You are DeepTutor, the AI tutor for the 'Backend System Design' course "
    "(a 15-week, 11-module backend engineering curriculum).\n"
    "Rules:\n"
    "1. Ground every answer in the COURSE EXCERPTS provided in the user message.\n"
    "2. Cite module codes like [M03] for claims drawn from the course.\n"
    "3. If the question goes beyond the course, say so in one clause, then answer briefly from general knowledge.\n"
    "4. Be concrete: rules, numbers, trade-offs, failure modes. No filler."
)


class TutorReq(BaseModel):
    question: str
    module: Optional[str] = None
    stream: bool = False


class QuizReq(BaseModel):
    module: Optional[str] = None
    count: int = 5


class ExplainReq(BaseModel):
    concept: str
    level: str = "simple"


def _llm_configured() -> bool:
    return bool(LLM_API_KEY)


def _messages_for(question: str, module: Optional[str], extra_system: str = "") -> list:
    chunks = KB.retrieve(question, module=module, k=4)
    excerpts = "\n\n".join(f"[{c['module']} · {c['title']}]\n{c['text']}" for c in chunks) or "(no excerpts matched)"
    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")
    user = f"COURSE EXCERPTS:\n{excerpts}\n\nQUESTION: {question}"
    if module:
        user += f"\n(The learner is currently studying module {module} — prefer excerpts from it.)"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], chunks


async def _chat(payload: dict):
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_json(text: str):
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "deeptutor-course-backend",
        "llm": {"configured": _llm_configured(), "base_url": LLM_BASE_URL, "model": LLM_MODEL},
        "kb": {"chunks": len(KB.chunks), "modules": KB.modules},
    }


@app.get("/api/outline")
async def outline():
    return {"modules": KB.modules}


@app.post("/api/tutor")
async def tutor(req: TutorReq):
    if not _llm_configured():
        return JSONResponse(status_code=503, content={"error": "LLM_API_KEY is not configured on this deployment."})
    messages, chunks = _messages_for(req.question, req.module)
    payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.3, "stream": req.stream}
    sources = [{"module": c["module"], "title": c["title"]} for c in chunks]

    if not req.stream:
        data = await _chat(payload)
        answer = data["choices"][0]["message"]["content"]
        return {"answer": answer, "sources": sources, "model": LLM_MODEL}

    async def gen():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                    except Exception:
                        continue
                    if delta:
                        yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/quiz")
async def quiz(req: QuizReq):
    if not _llm_configured():
        return JSONResponse(status_code=503, content={"error": "LLM_API_KEY is not configured on this deployment."})
    count = max(1, min(req.count, 10))
    topic = f"Focus on module {req.module}." if req.module else "Cover any course modules."
    q = (
        f"Generate {count} multiple-choice quiz questions strictly from the course excerpts. "
        f"{topic} Each question must be answerable from the excerpts alone. "
        'Return ONLY a JSON object: {"questions": [{"question": str, "options": [str, str, str, str], '
        '"answer": "A"|"B"|"C"|"D", "explanation": str}]}. '
        "Vary which option is correct across questions. Explanations: 1-2 sentences, cite module codes."
    )
    messages, chunks = _messages_for(q, req.module, extra_system="Output raw JSON only — no markdown fences, no prose.")
    data = await _chat({"model": LLM_MODEL, "messages": messages, "temperature": 0.5})
    try:
        parsed = _extract_json(data["choices"][0]["message"]["content"])
        questions = parsed.get("questions", [])[:count]
    except Exception:
        return JSONResponse(status_code=502, content={"error": "Model returned unparseable quiz JSON. Try again."})
    for i, item in enumerate(questions):
        item["id"] = f"gen-{i + 1}"
    return {"questions": questions, "sources": [{"module": c["module"], "title": c["title"]} for c in chunks]}


@app.post("/api/explain")
async def explain(req: ExplainReq):
    if not _llm_configured():
        return JSONResponse(status_code=503, content={"error": "LLM_API_KEY is not configured on this deployment."})
    level = "simple, with one concrete example" if req.level == "simple" else "in depth: mechanics, numbers, trade-offs, failure modes"
    q = f"Explain the concept '{req.concept}' at a {level}, grounded in the course excerpts."
    messages, chunks = _messages_for(q, None)
    data = await _chat({"model": LLM_MODEL, "messages": messages, "temperature": 0.3})
    return {
        "answer": data["choices"][0]["message"]["content"],
        "sources": [{"module": c["module"], "title": c["title"]} for c in chunks],
    }
