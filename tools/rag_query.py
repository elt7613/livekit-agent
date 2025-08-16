import logging
from livekit.agents import function_tool
import os
import aiohttp
from dotenv import load_dotenv
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get the base URL with validation
BASE_URL = os.environ.get("NEXUS_SERVICE_BASE_URL")
if not BASE_URL:
    logger.error("NEXUS_SERVICE_BASE_URL environment variable is not set")

@function_tool()
async def rag_query(
    workflow_id: str,
    query: str
) -> str:
    """
    Query data regarding the company/product/services using RAG (Retrieval-Augmented Generation).
    
    Args:
        workflow_id (str): The workflow ID for the collection to query.
        query (str): The search query.

    Returns:
        str: A string containing the query results.

    """
    url = f"{BASE_URL}/livekit/query-data"
    
    # Request body
    payload = {
        "workflow_id": workflow_id,
        "query": query
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Query result: {result['response']}")
                return str(result['response'])
    except Exception as e:
        logger.error(f"Failed to query data: {str(e)}")
        return f"Failed to query data: {str(e)}"