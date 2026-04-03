from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="My A2A Agent")

AGENT_CARD = {
    "name": "Inventory Helper Agent",
    "description": "Simple custom agent for A2A task",
    "version": "1.0.0",
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "capabilities": {
        "streaming": False,
        "pushNotifications": False
    },
    "supportedInterfaces": [
        {
            "protocolBinding": "JSONRPC",
            "url": "http://localhost:8080"
        }
    ],
    "skills": [
        {
            "id": "basic_info",
            "name": "Basic Info",
            "description": "Returns basic information",
            "tags": ["info", "demo"],
            "examples": ["who are you?", "what can you do?"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"]
        }
    ]
}

@app.get("/.well-known/agent-card.json")
def get_agent_card():
    return JSONResponse(content=AGENT_CARD)

@app.post("/message:send")
def send_message(payload: dict):
    user_text = ""
    try:
        parts = payload["message"]["parts"]
        if parts and "text" in parts[0]:
            user_text = parts[0]["text"]
    except Exception:
        pass

    return {
        "message": {
            "messageId": "resp-1",
            "role": "ROLE_AGENT",
            "parts": [
                {
                    "text": f"Hello from custom A2A agent. You said: {user_text}"
                }
            ]
        }
    }