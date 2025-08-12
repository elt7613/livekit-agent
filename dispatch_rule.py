import asyncio
from livekit import api
from dotenv import load_dotenv
import uuid,json

load_dotenv()


company_context = """
    **WuShoes – Summary**

WuShoes is an innovative footwear company focused on delivering high-quality, stylish, and comfortable shoes across diverse categories. Its core values include innovation, quality, sustainability, customer satisfaction, and continuous improvement.

**Key Highlights:**

* **Product Lines:** Lifestyle, Performance, Professional, and Specialized segments (including eco-friendly and orthopedic shoes).
* **Manufacturing:** High-tech, sustainable production with advanced materials and strict quality control.
* **Technology:** Emphasis on R\&D, biomechanical design, 3D prototyping, and digital tools like virtual try-ons.
* **Market Focus:** Urban professionals, athletes, fashion-forward individuals aged 16–55.
* **Sustainability:** Recyclable components, reduced carbon footprint, and ethical sourcing.
* **Customer Experience:** Strong online presence, personalized services, loyalty programs, and responsive support.
* **Future Goals:** Global expansion, new product innovation, enhanced digital platforms, and increased sustainability investments.

WuShoes positions itself not just as a footwear brand, but as a complete lifestyle solution.

    """

instructions = "you'll be reciving calls from delivery person and you'll have to guid them to leave the parcle neare the door and the adddress is itpl house 49 and leave the parcle near by the door where the dog is.the dog wont bite"

# Configuration
user_id = "elt7613"
system_agent_name = "appointment_agent" #"appointment_agent" #"bulk_calling_agent" #"personal_agent" #"customer_support_agent"
custom_instructions = None #"inform the user regarding the appointment for web 6th july 2025 is at 4pm and the take confirmation if he/she will be available. user's name ELT,email: elt@gmail,com,phone number: 1234567897"
workflow_id = str(uuid.uuid4()) #"a673504a-0733-4276-ae0b-24fb547c6faf" #str(uuid.uuid4())
#room_name = f"standalone-call-{workflow_id}"
agent_name = "Alita"
agent_gender = "Female"
agent_language = "multilingual"
#outbound_trunk_id = "ST_4iXEXw7jboku" #os.getenv("SIP_OUTBOUND_TRUNK_ID")
inbound_trunk_id = "ST_mabcYJL5Rvc2"
agent_number = "+19387585572"
# number_to_call = "+917795341235" #"+918770975421"
# number_from = "+15075123753"
company_name = "Wu shoes"
individual_name = None
knowledge_base = company_context
voice_id = "95d51f79-c397-46f9-b49a-23763d3eaa2d"
language_tts = "en"
llm_model = "openai/gpt-4.1-mini"
stt_model = "nova-3"
tts_model = "sonic-2"

campaign_objective = "geting feedback"
campaign_type = "feedback"
campaign_briefing = "want to get the feedback from the customers regarding the shoes taht hey bought from wushoes "
target_audience = "the perosns who bought the wushoes's shoes"
key_talking_points = "geeting the feed of wushoes from peoples"
objection_responses = "we'll note taht and improve it"

data = {
        "user_id":user_id,
        "system_agent_name":system_agent_name,
        "workflow_id":workflow_id,
        #"room_name":room_name,
        "agent_name":agent_name,
        "agent_gender":agent_gender,
        "agent_language":agent_language,
        "agent_number": agent_number,
        "inbound_trunk_id": inbound_trunk_id,
        # "number_from":number_from,
        # "number_to_call":number_to_call,
        # "outbound_sip_trunk_id":outbound_trunk_id,
        "tts_model":tts_model,
        "language_tts":language_tts,
        "voice_id":voice_id,
        "llm_model":llm_model,
        "stt_model":stt_model,
        "company_name":company_name,
        "individual_name":individual_name,
        "knowledge_base":knowledge_base,
        "custom_instructions":custom_instructions,
        "campaign_objective":campaign_objective,
        "campaign_type":campaign_type,
        "campaign_briefing":campaign_briefing,
        "target_audience":target_audience,
        "key_talking_points":key_talking_points,
        "objection_responses":objection_responses
    }

trunk_id = "ST_aArEp7NkAGXe"

async def main():
    lkapi = api.LiveKitAPI()

    # Create a dispatch rule to place each caller in a separate room
    rule = api.SIPDispatchRule(
        dispatch_rule_individual = api.SIPDispatchRuleIndividual(
            room_prefix = 'Inbound_Call-',
        )
    )

    request = api.CreateSIPDispatchRuleRequest(
        dispatch_rule = api.SIPDispatchRuleInfo(
            rule = rule,
            name = 'My dispatch rule',
            trunk_ids = [trunk_id],
            room_config=api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(
                    agent_name="Calling-Agent-System",
                    metadata=json.dumps(data),
                )]
            )
        )
    )

    dispatch = await lkapi.sip.create_sip_dispatch_rule(request)
    print("created dispatch", dispatch)
    await lkapi.aclose()

asyncio.run(main())

sip_dispatch_rule_id= "SDR_UzmnQon6y2vu"