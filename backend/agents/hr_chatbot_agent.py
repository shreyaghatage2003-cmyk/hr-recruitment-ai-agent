"""
HR Chatbot Agent — LangGraph stateful graph with RAG over DB.
All answers grounded in DB queries — no hallucination.
Nodes: classify_intent → execute_tool → format_response
Short-term memory: conversation history in state.
Long-term memory: reads exclusively from DB.
"""
import json
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from backend.services.mock_llm import get_llm
from backend.services.db_service import candidate_service, job_role_service
from backend.services.email_service import email_service
from backend.database.db import AsyncSessionLocal


class ChatState(TypedDict):
    session_id: str
    history: List[dict]
    user_message: str
    intent: str
    tool_result: str
    response: str
    error: Optional[str]


class HRChatbotAgent:
    def __init__(self):
        self._llm = None
        self.graph = self._build_graph()
        # In-memory session store (short-term memory)
        self._sessions: dict[str, List[dict]] = {}

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0)
        return self._llm

    def _build_graph(self) -> StateGraph:
        g = StateGraph(ChatState)
        g.add_node("classify_intent", self.classify_intent)
        g.add_node("execute_tool", self.execute_tool)
        g.add_node("format_response", self.format_response)

        g.set_entry_point("classify_intent")
        g.add_edge("classify_intent", "execute_tool")
        g.add_edge("execute_tool", "format_response")
        g.add_edge("format_response", END)
        return g.compile()

    async def classify_intent(self, state: ChatState) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify the HR user's intent. Return one of:
- list_candidates: user wants to see candidates (possibly filtered)
- get_candidate: user asks about a specific candidate
- update_stage: user wants to change a candidate's pipeline stage
- list_roles: user wants to see job roles
- create_role: user wants to create a new job role
- pipeline_summary: user wants counts/stats
- general: anything else

Return JSON: {{"intent": "<intent>", "params": {{...extracted params...}}}}"""),
            ("human", "{message}"),
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({"message": state["user_message"]})
        try:
            content = response.content.strip().strip("```json").strip("```").strip()
            data = json.loads(content)
            return {
                "intent": data.get("intent", "general"),
                "tool_result": json.dumps(data.get("params", {})),
            }
        except Exception:
            return {"intent": "general", "tool_result": "{}"}

    async def execute_tool(self, state: ChatState) -> dict:
        intent = state["intent"]
        try:
            params = json.loads(state["tool_result"])
        except Exception:
            params = {}

        async with AsyncSessionLocal() as db:
            if intent == "list_candidates":
                role_id = params.get("role_id")
                stage = params.get("stage")
                candidates = await candidate_service.list_all(db, role_id=role_id, stage=stage)
                data = [
                    {
                        "id": c.id, "name": c.name, "stage": c.pipeline_stage,
                        "ats_score": c.ats_score, "interview_score": c.interview_score,
                    }
                    for c in candidates
                ]
                return {"tool_result": json.dumps(data)}

            elif intent == "get_candidate":
                cid = params.get("candidate_id")
                name = params.get("name", "")
                if cid:
                    c = await candidate_service.get(db, cid)
                else:
                    all_c = await candidate_service.list_all(db)
                    c = next((x for x in all_c if name.lower() in x.name.lower()), None)
                if c:
                    return {"tool_result": json.dumps({
                        "id": c.id, "name": c.name, "email": c.email,
                        "stage": c.pipeline_stage, "ats_score": c.ats_score,
                        "interview_score": c.interview_score, "meeting_link": c.meeting_link,
                    })}
                return {"tool_result": json.dumps({"error": "Candidate not found"})}

            elif intent == "update_stage":
                cid = params.get("candidate_id")
                stage = params.get("stage")
                if cid and stage:
                    await candidate_service.update_stage(db, cid, stage)
                    return {"tool_result": json.dumps({"updated": True, "candidate_id": cid, "new_stage": stage})}
                return {"tool_result": json.dumps({"error": "Missing candidate_id or stage"})}

            elif intent == "list_roles":
                roles = await job_role_service.list_all(db)
                data = [
                    {"id": r.id, "title": r.title, "level": r.experience_level, "headcount": r.headcount_target}
                    for r in roles
                ]
                return {"tool_result": json.dumps(data)}

            elif intent == "create_role":
                role = await job_role_service.create(db, {
                    "title": params.get("title", "New Role"),
                    "description": params.get("description", ""),
                    "required_skills": params.get("required_skills", ""),
                    "experience_level": params.get("experience_level", "mid"),
                    "headcount_target": params.get("headcount_target", 1),
                })
                return {"tool_result": json.dumps({"created": True, "role_id": role.id, "title": role.title})}

            elif intent == "pipeline_summary":
                candidates = await candidate_service.list_all(db)
                stages: dict = {}
                for c in candidates:
                    stages[c.pipeline_stage] = stages.get(c.pipeline_stage, 0) + 1
                return {"tool_result": json.dumps({"total": len(candidates), "by_stage": stages})}

            else:
                return {"tool_result": json.dumps({"info": "I can help with candidate queries, stage updates, and role management."})}

    async def format_response(self, state: ChatState) -> dict:
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in state["history"][-6:]
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an HR assistant chatbot. Respond naturally based on the database results provided.
Do NOT invent any candidate names, scores, or data not present in the tool result.
Be concise and helpful."""),
            ("human", """Conversation so far:
{history}

User asked: {message}
Database result: {tool_result}

Respond naturally:"""),
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "history": history_text,
            "message": state["user_message"],
            "tool_result": state["tool_result"],
        })
        return {"response": response.content}

    async def chat(self, session_id: str, message: str) -> str:
        history = self._sessions.get(session_id, [])
        initial: ChatState = {
            "session_id": session_id,
            "history": history,
            "user_message": message,
            "intent": "",
            "tool_result": "",
            "response": "",
            "error": None,
        }
        result = await self.graph.ainvoke(initial)
        response = result["response"]

        # Update short-term session memory
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        self._sessions[session_id] = history[-20:]
        return response


hr_chatbot_agent = HRChatbotAgent()
