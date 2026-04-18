"""
Scheduling & Email Agent — LangGraph stateful graph.
Multi-agent pattern: coordinates with EmailAgent as a sub-operation.
Nodes: load_candidate → create_meeting → send_emails → persist
All I/O is async. Email log prevents duplicate sends.
"""
import asyncio
from datetime import datetime
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from backend.services.db_service import candidate_service, job_role_service
from backend.services.email_service import email_service
from backend.services.calendar_service import calendar_service
from backend.database.db import AsyncSessionLocal


class SchedulingState(TypedDict):
    candidate_id: int
    availability: List[dict]
    candidate_name: str
    candidate_email: str
    role_title: str
    job_role_id: int
    meeting_link: str
    interview_datetime: Optional[datetime]
    emails_sent: bool
    error: Optional[str]


class SchedulingAgent:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(SchedulingState)
        g.add_node("load_candidate", self.load_candidate)
        g.add_node("create_meeting", self.create_meeting)
        g.add_node("send_emails", self.send_emails)
        g.add_node("persist", self.persist)

        g.set_entry_point("load_candidate")
        g.add_conditional_edges("load_candidate", self._check_error, {"ok": "create_meeting", "error": END})
        g.add_conditional_edges("create_meeting", self._check_error, {"ok": "send_emails", "error": END})
        g.add_edge("send_emails", "persist")
        g.add_edge("persist", END)
        return g.compile()

    def _check_error(self, state: SchedulingState) -> str:
        return "error" if state.get("error") else "ok"

    async def load_candidate(self, state: SchedulingState) -> dict:
        async with AsyncSessionLocal() as db:
            candidate = await candidate_service.get(db, state["candidate_id"])
            if not candidate:
                return {"error": "Candidate not found"}
            role = await job_role_service.get(db, candidate.job_role_id)
            return {
                "candidate_name": candidate.name,
                "candidate_email": candidate.email,
                "role_title": role.title,
                "job_role_id": candidate.job_role_id,
            }

    async def create_meeting(self, state: SchedulingState) -> dict:
        slot = state["availability"][0] if state["availability"] else None
        if not slot:
            return {"error": "No availability provided"}
        try:
            dt_str = f"{slot['date']} {slot['time']}"
            interview_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except Exception:
            interview_dt = datetime.utcnow()

        result = await calendar_service.create_meeting(
            title=f"Interview: {state['candidate_name']} — {state['role_title']}",
            start_dt=interview_dt,
            attendee_emails=[state["candidate_email"]],
        )
        return {"meeting_link": result["link"], "interview_datetime": interview_dt}

    async def send_emails(self, state: SchedulingState) -> dict:
        async with AsyncSessionLocal() as db:
            already_sent = await candidate_service.email_already_sent(
                db, state["candidate_id"], "confirmation"
            )
            if already_sent:
                return {"emails_sent": False}

            dt_str = (
                state["interview_datetime"].strftime("%B %d, %Y at %H:%M UTC")
                if state["interview_datetime"]
                else "TBD"
            )
            candidate_ok, _ = await asyncio.gather(
                email_service.send_schedule_confirmation(
                    state["candidate_name"], state["candidate_email"],
                    state["role_title"], state["meeting_link"], dt_str,
                ),
                email_service.send_hr_notification(
                    state["candidate_name"], state["role_title"],
                    dt_str, state["meeting_link"],
                ),
            )
            await candidate_service.log_email(
                db, state["candidate_id"], "confirmation",
                state["candidate_email"], candidate_ok,
            )
        return {"emails_sent": candidate_ok}

    async def persist(self, state: SchedulingState) -> dict:
        async with AsyncSessionLocal() as db:
            await candidate_service.update_fields(db, state["candidate_id"], {
                "meeting_link": state["meeting_link"],
                "interview_datetime": state["interview_datetime"],
                "pipeline_stage": "scheduled",
            })
        return {"meeting_link": state["meeting_link"]}

    async def run(self, candidate_id: int, availability: List[dict]) -> dict:
        initial: SchedulingState = {
            "candidate_id": candidate_id,
            "availability": availability,
            "candidate_name": "",
            "candidate_email": "",
            "role_title": "",
            "job_role_id": 0,
            "meeting_link": "",
            "interview_datetime": None,
            "emails_sent": False,
            "error": None,
        }
        result = await self.graph.ainvoke(initial)
        if result.get("error"):
            return {"error": result["error"], "meeting_link": None}
        return {
            "meeting_link": result["meeting_link"],
            "interview_datetime": (
                result["interview_datetime"].isoformat()
                if result.get("interview_datetime")
                else None
            ),
            "emails_sent": result.get("emails_sent", False),
        }


scheduling_agent = SchedulingAgent()
