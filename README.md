# DeepTutor Course Backend

A Vercel-hosted tutoring API for the **Backend System Design** course
(<https://olivistart.com/backend-tutor/>), built on the DeepTutor approach
(HKUDS/DeepTutor): retrieval-grounded tutoring, quiz generation, and concept
explanation over a course knowledge base.

## What this is (and is not)

This is the **course-integration slice** of DeepTutor, packaged for Vercel's
serverless runtime: the course file (`api/course.md`) is parsed into a
module-scoped knowledge base at cold start, and an OpenAI-compatible LLM
configured via environment variables answers against it with module citations.

The **full DeepTutor app** (agent runtime, PocketBase auth, WebSocket streams,
FAISS/LlamaIndex knowledge bases, document parsing, the Next.js frontend) needs
a long-running host and persists state on disk — Vercel serverless is the wrong
shape for that. For the complete app, use the official image:

```
docker run --rm -p 127.0.0.1:3782:3782 -v deeptutor-data:/app/data ghcr.io/hkuds/deeptutor:latest
```

This backend gives the course page its tutor: same personalization idea, no
stateful dependencies, deploys in one command.

## API

| Endpoint | Method | Body | Returns |
|---|---|---|---|
| `/api/health` | GET | — | status, LLM config, KB stats |
| `/api/outline` | GET | — | the 11 course modules |
| `/api/tutor` | POST | `{question, module?, stream?}` | grounded answer + source modules (or SSE when `stream:true`) |
| `/api/quiz` | POST | `{module?, count?}` | `{questions:[{question, options[4], answer, explanation}]}` |
| `/api/explain` | POST | `{concept, level?}` | explanation at simple/deep depth |

CORS is pre-allowed for the course origins (`olivistart.com`,
`ericzhoun.github.io`) — override with `ALLOWED_ORIGINS`.

## Environment variables

| Var | Required | Default | Purpose |
|---|---|---|---|
| `LLM_API_KEY` | yes | — | API key for the LLM provider |
| `LLM_BASE_URL` | no | `https://open.bigmodel.cn/api/paas/v4` | OpenAI-compatible base URL |
| `LLM_MODEL` | no | `glm-4.6` | model name |
| `ALLOWED_ORIGINS` | no | course origins | comma-separated CORS list |

Any OpenAI-compatible provider works (Zhipu GLM, OpenAI, Moonshot, vLLM, …).

## Deploy

**Dashboard:** import this repo at vercel.com/new → add `LLM_API_KEY` → deploy.

**CLI:**

```
npm i -g vercel
vercel link
vercel env add LLM_API_KEY
vercel deploy --prod
```

Then set the deployment URL in the course page (`window.DEEPTUTOR_API` in
`index.html` of the `backend-tutor` repo) and the "Ask DeepTutor" panel goes
live.

## Local run

```
pip install -r requirements.txt
uvicorn api.index:app --port 8000   # then open /api/health
```
