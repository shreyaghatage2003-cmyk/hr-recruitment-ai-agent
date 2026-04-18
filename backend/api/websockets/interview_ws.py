"""
WebSocket endpoint for the timed technical interview.
Manages 30-second per-question timer enforcement on the backend.
"""
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from backend.agents.interview_agent import interview_agent


async def interview_websocket(websocket: WebSocket, candidate_id: int):
    await websocket.accept()
    try:
        # Step 1: Generate questions
        questions = await interview_agent.get_questions(candidate_id)
        await websocket.send_json({"type": "questions", "questions": questions})

        collected_answers = []

        for idx, question in enumerate(questions):
            # Send question with timer start signal
            await websocket.send_json({
                "type": "question",
                "index": idx,
                "question": question,
                "time_limit": 30,
            })

            answer = ""
            time_taken = 30
            start_time = asyncio.get_event_loop().time()

            try:
                # Wait for answer with 30s timeout
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                elapsed = asyncio.get_event_loop().time() - start_time
                time_taken = int(elapsed)
                data = json.loads(raw)
                answer = data.get("answer", "")
            except asyncio.TimeoutError:
                # Time's up — move on with empty answer
                await websocket.send_json({"type": "timeout", "index": idx})
                answer = ""
                time_taken = 30

            collected_answers.append({
                "question_index": idx,
                "answer": answer,
                "time_taken": time_taken,
            })

            await websocket.send_json({"type": "answer_received", "index": idx})

        # Step 2: Evaluate all answers
        result = await interview_agent.run(candidate_id, questions, collected_answers)
        await websocket.send_json({"type": "complete", "result": result})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
