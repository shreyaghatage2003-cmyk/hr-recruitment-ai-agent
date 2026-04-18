"""
WebSocket endpoint for the HR chatbot — real-time conversational interface.
"""
import json
from fastapi import WebSocket, WebSocketDisconnect
from backend.agents.hr_chatbot_agent import hr_chatbot_agent


async def chatbot_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            message = data.get("message", "")
            if not message:
                continue
            response = await hr_chatbot_agent.chat(session_id, message)
            await websocket.send_json({"type": "response", "message": response})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
