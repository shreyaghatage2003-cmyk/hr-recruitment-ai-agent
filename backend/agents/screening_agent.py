"""
HR Screening Agent — LangGraph stateful graph.
Nodes: load_candidate → generate_questions
Questions are derived from resume context — never ask what the resume already answers.
Short-term memory: state carries resume + role across nodes.
Long-term memory: save_answers writes to DB.
"""
import json
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from backend.services.mock_llm import get_llm
from backend.services.db_service import candidate_service, job_role_service
from backend.database.db import AsyncSessionLocal


class ScreeningState(TypedDict):
    candidate_id: int
    resume_text: str
    role_title: str
    experience_level: str
    questions: List[str]
    answers: List[dict]
    error: Optional[str]


class ScreeningAgent:
    def __init__(self):
        self._llm = None
        self.graph = self._build_graph()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.3)
        return self._llm

    def _build_graph(self) -> StateGraph:
        g = StateGraph(ScreeningState)
        g.add_node("load_candidate", self.load_candidate)
        g.add_node("generate_questions", self.generate_questions)

        g.set_entry_point("load_candidate")
        g.add_conditional_edges("load_candidate", self._check_error, {"ok": "generate_questions", "error": END})
        g.add_edge("generate_questions", END)
        return g.compile()

    def _check_error(self, state: ScreeningState) -> str:
        return "error" if state.get("error") else "ok"

    async def load_candidate(self, state: ScreeningState) -> dict:
        async with AsyncSessionLocal() as db:
            candidate = await candidate_service.get(db, state["candidate_id"])
            if not candidate:
                return {"error": "Candidate not found"}
            role = await job_role_service.get(db, candidate.job_role_id)
            return {
                "resume_text": candidate.resume_text,
                "role_title": role.title,
                "experience_level": role.experience_level,
            }

    async def generate_questions(self, state: ScreeningState) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an HR screener. Generate 5 contextual screening questions.
Rules:
- Do NOT ask anything already answered in the resume (name, skills, experience, education).
- Cover: notice period, expected joining date, work authorization, relocation willingness, salary expectations.
- For students/fresh grads: ask about graduation date, availability for full-time, internship expectations.
- Keep questions concise and professional.
Return JSON array: ["question1", ...]"""),
            ("human", """Role: {role_title} ({experience_level})
Resume:
{resume_text}"""),
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "role_title": state["role_title"],
            "experience_level": state["experience_level"],
            "resume_text": state["resume_text"][:3000],
        })
        try:
            content = response.content.strip().strip("```json").strip("```").strip()
            questions = json.loads(content)
        except Exception:
            questions = [response.content]
        return {"questions": questions}

    async def get_questions(self, candidate_id: int) -> List[str]:
        initial: ScreeningState = {
            "candidate_id": candidate_id,
            "resume_text": "",
            "role_title": "",
            "experience_level": "",
            "questions": [],
            "answers": [],
            "error": None,
        }
        result = await self.graph.ainvoke(initial)
        return result.get("questions", [])

    async def save_answers(self, candidate_id: int, answers: List[dict]) -> dict:
        async with AsyncSessionLocal() as db:
            await candidate_service.update_fields(db, candidate_id, {
                "screening_data": json.dumps(answers),
                "pipeline_stage": "scheduled",
            })
        return {"saved": True}


screening_agent = ScreeningAgent()
