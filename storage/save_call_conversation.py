import httpx
from typing import Any, Dict, List, Optional, Tuple
import os 
from dotenv import load_dotenv
load_dotenv()

NEXUS_SERVICE_BASE_URL = os.getenv("NEXUS_SERVICE_BASE_URL")

async def save_conversation(
    user_id: str,
    workflow_id: str,
    call_id: str,
    messages: List[Dict[str, Any]],
) -> str:
    """
    Save the call conversation in the database

    Args:
        user_id (str): The user id of the user
        workflow_id (str): The workflow id of the workflow
        call_id (str): The call id of the call
        messages (List[Dict[str, Any]]): The messages of the conversation

    Returns:
        str: The status code of the response
    """
    url = f"{NEXUS_SERVICE_BASE_URL}/livekit/add-call-conversation"
    payload = {
        "user_id": user_id,
        "workflow_id": workflow_id,
        "call_id": call_id,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
    except Exception:
        return f"Failed to save call conversation for user_id: {user_id}, workflow_id: {workflow_id}, call_id: {call_id}"
    return str(resp.status_code)
