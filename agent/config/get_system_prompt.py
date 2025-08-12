from prompts.customer_support import customer_support_english, customer_support_hindi, customer_support_multilingual
from prompts.personal_agent import personal_agent_english, personal_agent_hindi, personal_agent_multilingual
from prompts.bulk_calling_agent import bulk_calling_english,bulk_calling_hindi,bulk_calling_multilingual
from prompts.appointment_agent import appointment_agent_english,appointment_agent_hindi,appointment_agent_multilingual

def get_system_prompt(
    workflow_id: str,
    system_agent_name: str,
    agent_language: str,
    custom_instructions: str = None,
    company_name: str = None, 
    individual_name: str = None,
    agent_name: str = None,
    agent_gender: str = None,
    knowledge_base: str = None,
    campaign_objective: str = None,
    campaign_type: str = None,
    campaign_briefing: str = None,
    target_audience: str = None,
    key_talking_points: str = None,
    objection_responses: str = None
) -> str:
    """
    Get the system prompt for the given system agent name.
    
    Args:
        system_agent_name: str
        agent_language: str
        custom_instructions: str
        company_name: str
        individual_name: str
        agent_name: str
        agent_gender: str
        knowledge_base: str
        campaign_objective: str
        campaign_type: str
        campaign_briefing: str 
        target_audience: str
        key_talking_points: str 
        objection_responses: str
        
    Returns:
        str: The system prompt for the given system agent name.
    """
    system = {
        "customer_support_agent": {
            "english": customer_support_english.customer_support_english_prompt,
            "hindi": customer_support_hindi.customer_support_hindi_prompt,
            "multilingual": customer_support_multilingual.customer_support_multilingual_prompt
        },
        "personal_agent": {
            "english": personal_agent_english.personal_agent_english_prompt,
            "hindi": personal_agent_hindi.personal_agent_hindi_prompt,
            "multilingual": personal_agent_multilingual.personal_agent_multilingual_prompt
        },
        "bulk_calling_agent": {
            "english": bulk_calling_english.bulk_calling_agent_english_prompt,
            "hindi": bulk_calling_hindi.bulk_calling_agent_hindi_prompt,
            "multilingual": bulk_calling_multilingual.bulk_calling_agent_multilingual_prompt
        },
        "appointment_agent": {
            "english": appointment_agent_english.appointment_agent_english_prompt,
            "hindi": appointment_agent_hindi.appointment_agent_hindi_prompt,
            "multilingual": appointment_agent_multilingual.appointment_agent_multilingual_prompt
        }
    }
    
    prompt = system[system_agent_name][agent_language].format(
        workflow_id=workflow_id,
        custom_instructions=custom_instructions,
        company_name=company_name,
        individual_name=individual_name,
        agent_name=agent_name,
        agent_gender=agent_gender,  
        knowledge_base=knowledge_base,
        campaign_objective=campaign_objective,
        campaign_type=campaign_type,
        campaign_briefing=campaign_briefing,
        target_audience=target_audience,
        key_talking_points=key_talking_points,
        objection_responses=objection_responses
    )
    
    return prompt