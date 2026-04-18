"""
Mock LLM for demo mode — returns realistic fake responses when no OpenAI key is set.
Allows the full pipeline to run end-to-end without any API keys.
"""
import json
import random
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from typing import List, Optional, Any


class MockChatModel(BaseChatModel):
    """Fake LLM that returns plausible responses for each agent node."""

    model_name: str = "mock-gpt"

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        content = self._pick_response(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def _agenerate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)

    def _pick_response(self, messages: List[BaseMessage]) -> str:
        # Detect which node is calling based on system prompt keywords
        system_text = ""
        human_text = ""
        for m in messages:
            role = getattr(m, "type", "")
            if role == "system":
                system_text = m.content.lower()
            elif role == "human":
                human_text = m.content.lower()

        # ATS scoring
        if "ats scoring" in system_text or "score the resume" in system_text:
            score = random.uniform(72, 95)
            return json.dumps({
                "score": round(score, 1),
                "reasoning": f"Candidate shows strong alignment with required skills. "
                             f"Experience level matches the role requirements. "
                             f"Key technical keywords present in resume."
            })

        # Interview question generation
        if "generate interview questions" in system_text or "technical interviewer" in system_text:
            questions = [
                "What is the difference between a list and a tuple in Python?",
                "Explain how async/await works and when you would use it.",
                "What is a REST API and what are the main HTTP methods?",
                "How would you handle database connection pooling in a production app?",
                "Describe a time you debugged a difficult production issue.",
                "What is the difference between SQL and NoSQL databases?",
            ]
            return json.dumps(questions[:5])

        # Answer evaluation
        if "evaluating a technical interview answer" in system_text or "score 0-10" in system_text:
            score = random.uniform(5.0, 9.0) if human_text and len(human_text) > 20 else random.uniform(1.0, 4.0)
            return json.dumps({
                "score": round(score, 1),
                "reasoning": "Answer demonstrates reasonable understanding of the concept. "
                             "Could be more detailed but covers the key points."
            })

        # Screening question generation
        if "hr screener" in system_text or "screening questions" in system_text:
            questions = [
                "What is your current notice period?",
                "When would you be available to join if selected?",
                "Are you open to relocation if required?",
                "What are your salary expectations for this role?",
                "Do you require visa sponsorship to work in this location?",
            ]
            return json.dumps(questions)

        # Chatbot intent classification
        if "classify the hr" in system_text or "classify" in system_text:
            if any(w in human_text for w in ["candidate", "show", "list", "all"]):
                return json.dumps({"intent": "list_candidates", "params": {}})
            if any(w in human_text for w in ["summary", "count", "how many", "stats"]):
                return json.dumps({"intent": "pipeline_summary", "params": {}})
            if any(w in human_text for w in ["role", "job", "position"]):
                return json.dumps({"intent": "list_roles", "params": {}})
            return json.dumps({"intent": "general", "params": {}})

        # Chatbot response formatting
        if "hr assistant chatbot" in system_text or "respond naturally" in system_text:
            if "total" in human_text or "by_stage" in human_text:
                return "Here's the current pipeline summary based on the database."
            if "error" in human_text:
                return "I couldn't find that information in the database."
            return "Here's what I found in the database for you."

        # Default fallback
        return json.dumps({"result": "ok", "message": "Mock response"})


def get_llm(temperature: float = 0):
    """Return real ChatOpenAI if key is set, else MockChatModel."""
    from backend.config import settings
    if settings.has_openai:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=temperature, api_key=settings.openai_api_key)
    return MockChatModel()
