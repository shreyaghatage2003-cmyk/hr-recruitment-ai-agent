"""
Technical Interview Agent — LangGraph stateful graph.
Nodes: load_candidate → generate_questions → evaluate_answers → persist
Short-term memory: state carries resume + Q&A history across nodes.
Long-term memory: writes full Q&A + scores to DB.
"""
import json
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from backend.services.mock_llm import get_llm
from backend.services.db_service import candidate_service, job_role_service
from backend.database.db import AsyncSessionLocal


class QAItem(TypedDict):
    question: str
    answer: str
    score: float
    reasoning: str
    time_taken: int


class InterviewState(TypedDict):
    candidate_id: int
    resume_text: str
    role_title: str
    experience_level: str
    required_skills: str
    questions: List[str]
    raw_answers: List[dict]
    qa_results: List[QAItem]
    interview_score: float
    error: Optional[str]


class InterviewAgent:
    def __init__(self):
        self._llm = None
        self.graph = self._build_graph()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0.3)
        return self._llm

    def _build_graph(self) -> StateGraph:
        g = StateGraph(InterviewState)
        g.add_node("load_candidate", self.load_candidate)
        g.add_node("generate_questions", self.generate_questions)
        g.add_node("evaluate_answers", self.evaluate_answers)
        g.add_node("persist", self.persist)

        g.set_entry_point("load_candidate")
        g.add_conditional_edges("load_candidate", self._check_error, {"ok": "generate_questions", "error": END})
        g.add_edge("generate_questions", "evaluate_answers")
        g.add_edge("evaluate_answers", "persist")
        g.add_edge("persist", END)
        return g.compile()

    def _check_error(self, state: InterviewState) -> str:
        return "error" if state.get("error") else "ok"

    async def load_candidate(self, state: InterviewState) -> dict:
        async with AsyncSessionLocal() as db:
            candidate = await candidate_service.get(db, state["candidate_id"])
            if not candidate:
                return {"error": "Candidate not found"}
            role = await job_role_service.get(db, candidate.job_role_id)
            return {
                "resume_text": candidate.resume_text,
                "role_title": role.title,
                "experience_level": role.experience_level,
                "required_skills": role.required_skills,
            }

    async def generate_questions(self, state: InterviewState) -> dict:
        level_guidance = {
            "junior": "Focus on fundamentals, basic syntax, and simple problem-solving. 5 questions.",
            "mid": "Focus on design patterns, debugging, and moderate algorithms. 6 questions.",
            "senior": "Focus on system design, architecture trade-offs, and complex problem-solving. 7 questions.",
        }
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technical interviewer. Generate interview questions.
{level_guidance}
Questions must be answerable in 30 seconds of typing (concise, specific).
Return JSON array: ["question1", "question2", ...]"""),
            ("human", """Role: {role_title}
Level: {experience_level}
Required Skills: {required_skills}
Candidate Resume Summary: {resume_summary}"""),
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "level_guidance": level_guidance.get(state["experience_level"], level_guidance["mid"]),
            "role_title": state["role_title"],
            "experience_level": state["experience_level"],
            "required_skills": state["required_skills"],
            "resume_summary": state["resume_text"][:2000],
        })
        try:
            content = response.content.strip().strip("```json").strip("```").strip()
            questions = json.loads(content)
        except Exception:
            questions = [response.content]
        return {"questions": questions}

    async def evaluate_answers(self, state: InterviewState) -> dict:
        qa_results: List[QAItem] = []
        for ans_data in state["raw_answers"]:
            idx = ans_data["question_index"]
            question = state["questions"][idx] if idx < len(state["questions"]) else "Unknown question"
            answer = ans_data["answer"]
            time_taken = ans_data.get("time_taken", 30)

            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are evaluating a technical interview answer.
Score 0-10. Return JSON: {{"score": <float>, "reasoning": "<brief>"}}
If answer is empty or clearly copy-pasted (too long for 30s), score 0."""),
                ("human", """Role: {role_title} ({experience_level})
Question: {question}
Answer: {answer}
Time taken: {time_taken}s (max 30s)"""),
            ])
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "role_title": state["role_title"],
                "experience_level": state["experience_level"],
                "question": question,
                "answer": answer,
                "time_taken": time_taken,
            })
            try:
                content = response.content.strip().strip("```json").strip("```").strip()
                data = json.loads(content)
                score = float(data["score"])
                reasoning = data["reasoning"]
            except Exception:
                score = 0.0
                reasoning = response.content

            qa_results.append({
                "question": question,
                "answer": answer,
                "score": score,
                "reasoning": reasoning,
                "time_taken": time_taken,
            })

        avg_score = sum(q["score"] for q in qa_results) / len(qa_results) if qa_results else 0.0
        return {"qa_results": qa_results, "interview_score": round(avg_score * 10, 2)}

    async def persist(self, state: InterviewState) -> dict:
        async with AsyncSessionLocal() as db:
            await candidate_service.update_fields(db, state["candidate_id"], {
                "interview_qa": json.dumps(state["qa_results"]),
                "interview_score": state["interview_score"],
                "pipeline_stage": "screening",
            })
        return {"interview_score": state["interview_score"]}

    async def get_questions(self, candidate_id: int) -> List[str]:
        """Called before interview starts — returns generated questions for the session."""
        initial: InterviewState = {
            "candidate_id": candidate_id,
            "resume_text": "",
            "role_title": "",
            "experience_level": "",
            "required_skills": "",
            "questions": [],
            "raw_answers": [],
            "qa_results": [],
            "interview_score": 0.0,
            "error": None,
        }
        load_result = await self.load_candidate(initial)
        initial.update(load_result)
        if initial.get("error"):
            return []
        gen_result = await self.generate_questions(initial)
        return gen_result["questions"]

    async def run(self, candidate_id: int, questions: List[str], raw_answers: List[dict]) -> dict:
        initial: InterviewState = {
            "candidate_id": candidate_id,
            "resume_text": "",
            "role_title": "",
            "experience_level": "",
            "required_skills": "",
            "questions": questions,
            "raw_answers": raw_answers,
            "qa_results": [],
            "interview_score": 0.0,
            "error": None,
        }
        load_result = await self.load_candidate(initial)
        initial.update(load_result)
        if initial.get("error"):
            return {"interview_score": 0.0, "qa_results": [], "error": initial["error"]}
        eval_result = await self.evaluate_answers(initial)
        initial.update(eval_result)
        await self.persist(initial)
        return {
            "interview_score": initial["interview_score"],
            "qa_results": initial["qa_results"],
        }


interview_agent = InterviewAgent()
