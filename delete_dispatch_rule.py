import asyncio
from livekit import api
from dotenv import load_dotenv

load_dotenv()

sip_dispatch_rule_id= "SDR_JsKTekPDzy37"

async def main():
    
    livekit_api = api.LiveKitAPI()
    
    res = await livekit_api.sip.delete_sip_dispatch_rule(
        api.DeleteSIPDispatchRuleRequest(
            sip_dispatch_rule_id=sip_dispatch_rule_id
        )
    )
    print(res)
    await livekit_api.aclose()

asyncio.run(main())
