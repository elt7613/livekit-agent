from livekit.agents import function_tool

@function_tool()
async def check_appointment_availability(date: str,time: str) -> str:
    """
    Check appointment availability for a given date and time.

    Args:
        date (str): The date to check availability for.
        time (str): The time to check availability for.
    
    Returns:
        str: A string containing the availability status.
    """
    return f"Appointment available on {date} at {time}"