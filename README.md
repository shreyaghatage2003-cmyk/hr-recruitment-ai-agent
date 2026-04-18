# HR Recruitment Agent System

> Agentic AI Engineering — Assignment 1  
> Stack: Python · LangGraph · FastAPI · SQLite · Vanilla JS

An end-to-end AI-powered HR recruitment pipeline that automates the journey from resume submission to interview scheduling, with an HR dashboard and conversational interface.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CANDIDATE PORTAL                         │
│                     http://localhost:8000                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ POST /api/candidates/upload
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  ATS AGENT (LangGraph)                                           │
│  parse_resume → fetch_job → score_ats → persist → send_rejection│
│  Short-term: ATSState TypedDict (resume, score, flags)           │
│  Long-term:  writes candidate + ATS score to SQLite              │
└──────────┬───────────────────────────┬───────────────────────────┘
     score ≥ 80%                  score < 80%
           │                           │
           ▼                           ▼
  pipeline_stage =            rejection email sent
    "ats_passed"               (SendGrid / mock)
           │
           │  WebSocket /ws/interview/{id}
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  INTERVIEW AGENT (LangGraph)                                     │
│  load_candidate → generate_questions → evaluate_answers → persist│
│  Short-term: InterviewState (resume, questions, Q&A history)     │
│  Long-term:  writes interview_qa + interview_score to SQLite     │
│  Enforcement: asyncio.wait_for(timeout=30s) per question         │
└──────────┬───────────────────────────────────────────────────────┘
           │  GET /api/screening/{id}/questions
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  SCREENING AGENT (LangGraph)                                     │
│  load_candidate → generate_questions                             │
│  Short-term: ScreeningState (resume, role, questions)            │
│  Long-term:  writes screening_data to SQLite                     │
│  Questions derived from resume — never duplicates resume content │
└──────────┬───────────────────────────────────────────────────────┘
           │  POST /api/scheduling/schedule
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  SCHEDULING AGENT (LangGraph)  ←── multi-agent coordination      │
│  load_candidate → create_meeting → send_emails → persist         │
│  Short-term: SchedulingState (candidate, slot, link, emails)     │
│  Long-term:  writes meeting_link + interview_datetime to SQLite  │
│  Emails: asyncio.gather (candidate + HR concurrently)            │
│  Dedup:  EmailLog table prevents duplicate sends                 │
└──────────┬───────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     SQLITE DATABASE                              │
│  tables: candidates, job_roles, email_logs                       │
│  ORM: SQLAlchemy async (aiosqlite)                               │
└──────────┬───────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  HR DASHBOARD  http://localhost:8000/dashboard.html              │
│  - Pipeline table (all candidates, filters by role + stage)      │
│  - Stage update per candidate                                    │
│  - Create new job roles                                          │
│  - Stats grid (total, ATS passed, scheduled, hired, rejected)    │
└──────────┬───────────────────────────────────────────────────────┘
           │  WebSocket /ws/chatbot/{session_id}
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  HR CHATBOT AGENT (LangGraph)                                    │
│  classify_intent → execute_tool → format_response                │
│  Short-term: ChatState (session history, last 20 turns)          │
│  Long-term:  reads exclusively from SQLite — no hallucination    │
│  Intents: list_candidates, get_candidate, update_stage,          │
│           list_roles, create_role, pipeline_summary              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Technology Choices & Justification

| Component | Choice | Justification |
|-----------|--------|---------------|
| Backend | **FastAPI + Python** | Mandatory. Async-native, first-class WebSocket support, auto Swagger docs via Pydantic |
| Agent Framework | **LangGraph** | Mandatory. Stateful graphs with explicit nodes, edges, and conditional routing — not achievable with plain function chains |
| LLM | **OpenAI GPT-4o** | Best reasoning for ATS scoring, interview evaluation, and intent classification. Falls back to `MockChatModel` if key absent |
| Database | **SQLite + SQLAlchemy async** | Zero-config, single file, fully portable for demo. Swap to PostgreSQL by changing `DATABASE_URL` only |
| Frontend | **Vanilla HTML/JS** | No build step, instant demo, no framework overhead. WebSocket API built-in to browsers |
| Email | **SendGrid** | Free tier, reliable delivery, simple Python SDK. Falls back to log-only mode if key absent |
| Calendar | **Google Calendar API** | Free, widely used. Falls back to Jitsi Meet link automatically if credentials not configured |

---

## Memory Implementation

### Short-Term Memory (Session State)
Every agent defines a `TypedDict` state that LangGraph carries across all nodes in a single execution. No data is re-fetched between nodes.

```python
# Example: ATS Agent state
class ATSState(TypedDict):
    file_bytes: bytes       # set at entry
    resume_text: str        # set by parse_resume node
    ats_score: float        # set by score_ats node
    candidate_id: int       # set by persist node
    passed: bool            # used by conditional edge
    ...
```

Applies to: ATS Agent, Interview Agent, Screening Agent, HR Chatbot

### Long-Term Memory (Persistent)
Every agent writes its output to SQLite **before** handing off to the next stage. The HR Chatbot answers queries **exclusively** from DB — never from LLM memory.

```python
# Every agent ends with a persist node
async def persist(self, state):
    await candidate_service.update_fields(db, state["candidate_id"], {
        "interview_score": state["interview_score"],
        "pipeline_stage": "screening",
    })
```

---

## Project Structure

```
hr-recruitment-agent/
├── backend/
│   ├── agents/
│   │   ├── ats_agent.py          # Resume ingestion + ATS scoring
│   │   ├── interview_agent.py    # Timed technical interview
│   │   ├── screening_agent.py    # HR screening questions
│   │   ├── scheduling_agent.py   # Calendar + email coordination
│   │   └── hr_chatbot_agent.py   # Conversational HR assistant
│   ├── api/
│   │   ├── routes/
│   │   │   ├── candidates.py     # POST /upload, GET /, PATCH /stage
│   │   │   ├── interview.py      # GET /questions, POST /submit
│   │   │   ├── screening.py      # GET /questions, POST /submit
│   │   │   ├── scheduling.py     # POST /schedule
│   │   │   └── dashboard.py      # GET /summary, GET+POST /roles
│   │   └── websockets/
│   │       ├── interview_ws.py   # 30s timer enforcement
│   │       └── chatbot_ws.py     # Real-time HR chatbot
│   ├── models/
│   │   ├── candidate.py          # SQLAlchemy ORM (Candidate, EmailLog)
│   │   ├── job_role.py           # SQLAlchemy ORM (JobRole)
│   │   └── schemas.py            # Pydantic request/response models
│   ├── services/
│   │   ├── db_service.py         # Async CRUD (CandidateService, JobRoleService)
│   │   ├── resume_parser.py      # PDF/DOCX text extraction
│   │   ├── email_service.py      # SendGrid wrapper (mock fallback)
│   │   ├── calendar_service.py   # Google Calendar (Jitsi fallback)
│   │   └── mock_llm.py           # MockChatModel for keyless demo
│   ├── database/db.py            # SQLAlchemy async engine + init_db
│   ├── config.py                 # Pydantic Settings from .env
│   └── main.py                   # FastAPI app, routers, WebSockets, static
├── frontend/
│   ├── index.html                # Candidate application page
│   ├── interview.html            # Interview + screening + scheduling
│   ├── dashboard.html            # HR pipeline dashboard + chatbot
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── dashboard.js
│           └── interview.js
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/hr-recruitment-agent.git
cd hr-recruitment-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```
Edit `.env` and fill in:
```
OPENAI_API_KEY=sk-...          # Required for real LLM scoring
SENDGRID_API_KEY=SG....        # Optional — emails logged to console if absent
SENDGRID_FROM_EMAIL=hr@yourcompany.com
HR_EMAIL=hr@yourcompany.com
```
> **Demo mode:** If `OPENAI_API_KEY` is not set, the system runs with a `MockChatModel` that returns realistic fake scores and questions — the full pipeline works end-to-end.

### 4. Run the server
```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Open in browser
| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Candidate resume submission |
| http://localhost:8000/dashboard.html | HR pipeline dashboard + chatbot |
| http://localhost:8000/interview.html?id=`<id>` | Technical interview |
| http://localhost:8000/docs | Auto-generated API docs (Swagger) |

---

## Full Pipeline Demo Walkthrough

1. Go to **http://localhost:8000** → select a job role → upload a PDF/DOCX resume
2. ATS Agent scores the resume (0–100). Score ≥ 80 → shortlisted. Score < 80 → rejection email sent.
3. Click the interview link → 30-second timer starts per question, paste is disabled
4. After all questions → HR Screening questions appear (contextual, resume-derived)
5. Submit screening → pick availability date/time → meeting link generated, emails sent
6. Go to **http://localhost:8000/dashboard.html** → see candidate in pipeline
7. Use the chatbot: *"Show me all candidates"*, *"How many are scheduled?"*, *"Move candidate 1 to hired"*

---

## Skill Coverage Map

| Skill | Where in code |
|-------|--------------|
| LangGraph / Stateful Graphs | All 5 agents — `StateGraph`, `add_node`, `add_edge`, `add_conditional_edges` |
| Multi-Agent Patterns | `SchedulingAgent` coordinates `EmailService`; `HRChatbotAgent` triggers role creation |
| Short-Term Memory | `ATSState`, `InterviewState`, `ScreeningState`, `ChatState` TypedDicts |
| Long-Term Memory | `persist` nodes in every agent; HR Chatbot reads only from DB |
| Prompt Engineering | Interview questions calibrated by level; screening avoids resume duplicates |
| RAG | ATS scores over JD text; HR Chatbot queries DB before LLM formats response |
| Evaluation | LLM scores each interview answer 0–10 with reasoning in `evaluate_answers` node |
| Human-in-the-Loop | 30s `asyncio.wait_for` backend enforcement; HR stage changes via chatbot |
| Tools | All agents use LangChain tool-call pattern via `ChatPromptTemplate` chains |
| FastAPI / REST | 5 routers, 12 endpoints, Pydantic validation throughout |
| WebSockets | `/ws/interview/{id}` for timer; `/ws/chatbot/{session_id}` for chatbot |
| Pydantic | `CandidateOut`, `ScheduleRequest`, `ScreeningSubmission`, etc. in `schemas.py` |
| Database Connectivity | SQLAlchemy async ORM, `AsyncSession`, `aiosqlite` |
| Python OOP + Async | Agent classes, service layer, all I/O uses `async/await` |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/candidates/upload` | Upload resume → ATS scoring |
| GET | `/api/candidates/` | List candidates (filter: role_id, stage) |
| GET | `/api/candidates/{id}` | Get single candidate |
| PATCH | `/api/candidates/{id}/stage` | Update pipeline stage |
| GET | `/api/interview/{id}/questions` | Generate interview questions |
| POST | `/api/interview/submit` | Submit + evaluate answers |
| GET | `/api/screening/{id}/questions` | Generate screening questions |
| POST | `/api/screening/submit` | Save screening answers |
| POST | `/api/scheduling/schedule` | Create meeting + send emails |
| GET | `/api/dashboard/summary` | Pipeline stats |
| GET | `/api/dashboard/roles` | List job roles |
| POST | `/api/dashboard/roles` | Create job role |
| WS | `/ws/interview/{candidate_id}` | Timed interview WebSocket |
| WS | `/ws/chatbot/{session_id}` | HR chatbot WebSocket |
