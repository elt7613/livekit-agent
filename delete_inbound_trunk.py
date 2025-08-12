import asyncio
from livekit import api
from dotenv import load_dotenv
from livekit.protocol.sip import DeleteSIPTrunkRequest

load_dotenv()

trunk_id = "ST_mabcYJL5Rvc2"

async def main():
    
    livekit_api = api.LiveKitAPI()
    
    res = await livekit_api.sip.delete_sip_trunk(
        DeleteSIPTrunkRequest(
            sip_trunk_id=trunk_id
        )
    )
    print(res)
    await livekit_api.aclose()

asyncio.run(main())
