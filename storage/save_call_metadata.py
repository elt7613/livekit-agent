import httpx
from typing import Any, Dict, List, Optional, Tuple
import os 
from dotenv import load_dotenv
load_dotenv()

NEXUS_SERVICE_BASE_URL = os.getenv("NEXUS_SERVICE_BASE_URL")

async def save_metadata(
    user_id: str,
    workflow_id: str,
    call_id: str,
    metadata: Any
) -> str:
    """
    Save the call metadata in the database

    Args:
        user_id (str): The user id of the user
        workflow_id (str): The workflow id of the workflow
        call_id (str): The call id of the call
        metadata (Any): The metadata of the call

    Returns:
        str: The status code of the response
    """
    url = f"{NEXUS_SERVICE_BASE_URL}/livekit/add-call-metadata"

    payload = {
        "user_id": user_id,
        "workflow_id": workflow_id,
        "call_id": call_id,
        "metadata": metadata,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url,json=payload)
    except Exception:
        return f"Failed to save call metadata for user_id: {user_id}, workflow_id: {workflow_id}, call_id: {call_id}"
    return f"{resp.status_code}"