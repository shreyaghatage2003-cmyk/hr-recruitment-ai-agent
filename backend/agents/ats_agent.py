"""
ATS Agent — LangGraph stateful graph.
Nodes: parse_resume → fetch_job → score_ats → persist → (conditional) send_rejection
Short-term memory: state carries parsed resume + score across nodes (no re-fetching).
Long-term memory: writes to DB before handoff.
"""
import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from backend.services.mock_llm import get_llm
from backend.services.resume_parser import resume_parser
from backend.services.db_service import candidate_service, job_role_service
from backend.services.email_service import email_service
from backend.database.db import AsyncSessionLocal


class ATSState(TypedDict):
    file_bytes: bytes
    filename: str
    job_role_id: int
    resume_text: str
    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str]
    job_description: str
    required_skills: str
    experience_level: str
    role_title: str
    ats_score: float
    ats_reasoning: str
    candidate_id: Optional[int]
    passed: bool
    error: Optional[str]


class ATSAgent:
    def __init__(self):
        self._llm = None
        self.graph = self._build_graph()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0)
        return self._llm

    def _build_graph(self) -> StateGraph:
        g = StateGraph(ATSState)
        g.add_node("parse_resume", self.parse_resume)
        g.add_node("fetch_job", self.fetch_job)
        g.add_node("score_ats", self.score_ats)
        g.add_node("persist", self.persist)
        g.add_node("send_rejection", self.send_rejection)

        g.set_entry_point("parse_resume")
        g.add_edge("parse_resume", "fetch_job")
        g.add_conditional_edges("fetch_job", self._check_error, {"ok": "score_ats", "error": END})
        g.add_edge("score_ats", "persist")
        g.add_conditional_edges("persist", self._route, {"reject": "send_rejection", "pass": END})
        g.add_edge("send_rejection", END)
        return g.compile()

    def _check_error(self, state: ATSState) -> str:
        return "error" if state.get("error") else "ok"

    def _route(self, state: ATSState) -> str:
        return "pass" if state["passed"] else "reject"

    async def parse_resume(self, state: ATSState) -> dict:
        parsed = resume_parser.parse(state["file_bytes"], state["filename"])
        return {
            "resume_text": parsed["text"],
            "candidate_name": parsed["name"],
            "candidate_email": parsed["email"] or "",
            "candidate_phone": parsed["phone"],
        }

    async def fetch_job(self, state: ATSState) -> dict:
        async with AsyncSessionLocal() as db:
            role = await job_role_service.get(db, state["job_role_id"])
            if not role:
                return {"error": "Job role not found"}
            return {
                "job_description": role.description,
                "required_skills": role.required_skills,
                "experience_level": role.experience_level,
                "role_title": role.title,
            }

    async def score_ats(self, state: ATSState) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an ATS scoring engine. Score the resume against the job description.
Evaluate: skill match, experience alignment, keyword relevance.
Return JSON: {{"score": <0-100 float>, "reasoning": "<concise explanation>"}}
Score 80+ means the candidate passes."""),
            ("human", """Job Title: {role_title}
Experience Level: {experience_level}
Required Skills: {required_skills}
Job Description: {job_description}

Resume:
{resume_text}"""),
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "role_title": state["role_title"],
            "experience_level": state["experience_level"],
            "required_skills": state["required_skills"],
            "job_description": state["job_description"],
            "resume_text": state["resume_text"][:4000],
        })
        try:
            content = response.content.strip().strip("```json").strip("```").strip()
            data = json.loads(content)
            score = float(data["score"])
            reasoning = data["reasoning"]
        except Exception:
            score = 0.0
            reasoning = response.content
        return {"ats_score": score, "ats_reasoning": reasoning, "passed": score >= 80.0}

    async def persist(self, state: ATSState) -> dict:
        stage = "ats_passed" if state["passed"] else "ats_rejected"
        async with AsyncSessionLocal() as db:
            existing = await candidate_service.get_by_email(db, state["candidate_email"])
            if existing:
                updated = await candidate_service.update_fields(db, existing.id, {
                    "ats_score": state["ats_score"],
                    "ats_reasoning": state["ats_reasoning"],
                    "pipeline_stage": stage,
                })
                return {"candidate_id": updated.id, "passed": state["passed"]}
            candidate = await candidate_service.create(db, {
                "name": state["candidate_name"],
                "email": state["candidate_email"],
                "phone": state["candidate_phone"],
                "resume_text": state["resume_text"],
                "resume_filename": state["filename"],
                "job_role_id": state["job_role_id"],
                "ats_score": state["ats_score"],
                "ats_reasoning": state["ats_reasoning"],
                "pipeline_stage": stage,
            })
        return {"candidate_id": candidate.id, "passed": state["passed"]}

    async def send_rejection(self, state: ATSState) -> dict:
        async with AsyncSessionLocal() as db:
            already_sent = await candidate_service.email_already_sent(db, state["candidate_id"], "rejection")
            if not already_sent:
                success = await email_service.send_rejection(
                    state["candidate_name"], state["candidate_email"], state["role_title"]
                )
                await candidate_service.log_email(
                    db, state["candidate_id"], "rejection", state["candidate_email"], success
                )
        return {"error": state.get("error")}  # preserve state, return at least one key

    async def run(self, file_bytes: bytes, filename: str, job_role_id: int) -> dict:
        initial: ATSState = {
            "file_bytes": file_bytes,
            "filename": filename,
            "job_role_id": job_role_id,
            "resume_text": "",
            "candidate_name": "",
            "candidate_email": "",
            "candidate_phone": None,
            "job_description": "",
            "required_skills": "",
            "experience_level": "",
            "role_title": "",
            "ats_score": 0.0,
            "ats_reasoning": "",
            "candidate_id": None,
            "passed": False,
            "error": None,
        }
        result = await self.graph.ainvoke(initial)
        return {
            "candidate_id": result["candidate_id"],
            "ats_score": result["ats_score"],
            "reasoning": result["ats_reasoning"],
            "passed": result["passed"],
            "candidate_name": result["candidate_name"],
            "candidate_email": result["candidate_email"],
        }


ats_agent = ATSAgent()
