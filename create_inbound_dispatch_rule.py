import asyncio
from livekit import api
from dotenv import load_dotenv
import json
import os

load_dotenv()

# Configuration for inbound calls
inbound_trunk_id = "ST_aArEp7NkAGXe"  # Your inbound trunk ID

# Inbound call configuration
inbound_data = {
    "user_id": "elt",
    "system_agent_name": "appointment_agent",
    "call_type": "inbound",
    "agent_name": "Alita",
    "agent_gender": "Female",
    "agent_language": "multilingual",
    "tts_model": "sonic-2",
    "language_tts": "en",
    "voice_id": "95d51f79-c397-46f9-b49a-23763d3eaa2d",
    "llm_model": "openai/gpt-4.1-mini",
    "stt_model": "nova-3",
    "company_name": "Wu shoes",
    "knowledge_base": """
    **WuShoes – Summary**

WuShoes is an innovative footwear company focused on delivering high-quality, stylish, and comfortable shoes across diverse categories. Its core values include innovation, quality, sustainability, customer satisfaction, and continuous improvement.

**Key Highlights:**

* **Product Lines:** Lifestyle, Performance, Professional, and Specialized segments (including eco-friendly and orthopedic shoes).
* **Manufacturing:** High-tech, sustainable production with advanced materials and strict quality control.
* **Technology:** Emphasis on R&D, biomechanical design, 3D prototyping, and digital tools like virtual try-ons.
* **Market Focus:** Urban professionals, athletes, fashion-forward individuals aged 16–55.
* **Sustainability:** Recyclable components, reduced carbon footprint, and ethical sourcing.
* **Customer Experience:** Strong online presence, personalized services, loyalty programs, and responsive support.
* **Future Goals:** Global expansion, new product innovation, enhanced digital platforms, and increased sustainability investments.

WuShoes positions itself not just as a footwear brand, but as a complete lifestyle solution.
    """,
    "custom_instructions": "You are receiving inbound calls from customers. Please be helpful and professional.",
    "campaign_objective": "customer_service",
    "campaign_type": "inbound_support",
    "campaign_briefing": "Handle customer inquiries about WuShoes products and services.",
    "target_audience": "Customers calling WuShoes customer service",
    "key_talking_points": "Product information, order status, returns and exchanges, general inquiries",
    "objection_responses": "We'll note that and improve it."
}

async def main():
    lkapi = api.LiveKitAPI()

    # Create a dispatch rule for inbound calls
    rule = api.SIPDispatchRule(
        dispatch_rule_individual = api.SIPDispatchRuleIndividual(
            room_prefix = 'inbound-call-',
        )
    )

    request = api.CreateSIPDispatchRuleRequest(
        dispatch_rule = api.SIPDispatchRuleInfo(
            rule = rule,
            name = 'Inbound Dispatch Rule',
            trunk_ids = [inbound_trunk_id],
            room_config=api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(
                    agent_name="Calling-Agent-System",
                    metadata=json.dumps(inbound_data),
                )]
            )
        )
    )

    dispatch = await lkapi.sip.create_sip_dispatch_rule(request)
    print("Created inbound dispatch rule:", dispatch)
    await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())
