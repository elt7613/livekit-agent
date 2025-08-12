from datetime import datetime
import pytz
from livekit.agents import function_tool

@function_tool()
async def get_date() -> str:
    """
    Get the current date.
    
    Returns:
        str: Current date in format 'DD-MM-YYYY'
    """
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    return current_time.strftime("%d-%m-%Y")

@function_tool()
async def get_time() -> str:
    """
    Get the current time with AM/PM format.
    
    Returns:
        str: Current time in format 'HH:MM:SS AM/PM'
    """
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    return current_time.strftime("%I:%M %p")
