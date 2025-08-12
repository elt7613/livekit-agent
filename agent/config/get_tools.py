from tools.date_time import get_date, get_time
from tools.rag_query import rag_query
from tools.appointment_calender import check_appointment_availability

def get_tools(system_agent_name: str) -> list:
    """
    Get the tools for the given system agent name.
    """
    tools = {
        "customer_support_agent": [
            get_date, 
            get_time,
            rag_query
        ],
        "personal_agent": [
            get_date, 
            get_time,
            rag_query
        ],
        "bulk_calling_agent": [
            get_date, 
            get_time,
            rag_query
        ],
        "appointment_agent": [
            get_date, 
            get_time,
            rag_query,
            check_appointment_availability
        ]
    }
    
    return tools[system_agent_name]