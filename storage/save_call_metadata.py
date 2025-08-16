import httpx
from typing import Any, Dict, List, Optional, Tuple
import os
import asyncio
import random
from dotenv import load_dotenv
load_dotenv()

NEXUS_SERVICE_BASE_URL = os.getenv("NEXUS_SERVICE_BASE_URL")

async def save_metadata(
    user_id: str,
    workflow_id: str,
    call_id: str,
    metadata: Any,
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

    # Idempotency key ensures retried POSTs are treated as the same operation by the server
    idempotency_key = f"livekit:metadata:{call_id}"
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
    }

    # Retry with exponential backoff and jitter for transient failures
    max_attempts = 5
    delay = 0.5  # seconds
    timeout = httpx.Timeout(10.0)

    retriable_statuses = {408, 429, 500, 502, 503, 504}
    last_error: Optional[str] = None
    last_status: Optional[int] = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                status = resp.status_code
                last_status = status
                # Success or non-retriable status codes
                if 200 <= status < 300:
                    return str(status)
                if status not in retriable_statuses:
                    return str(status)
                last_error = f"HTTP {status}"
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as e:
                last_error = f"Network error: {e}"
            except Exception as e:
                # Unexpected error; do not retry to avoid hidden bugs
                return (
                    f"Failed to save call metadata for user_id: {user_id}, workflow_id: {workflow_id}, "
                    f"call_id: {call_id}. Error: {e}"
                )

            # Backoff if more attempts remain
            if attempt < max_attempts:
                jitter = random.uniform(0.8, 1.2)
                await asyncio.sleep(delay * jitter)
                delay *= 2

    # Exhausted retries
    return (
        f"Failed to save call metadata for user_id: {user_id}, workflow_id: {workflow_id}, call_id: {call_id}. "
        f"Last status: {last_status}, Last error: {last_error}"
    )