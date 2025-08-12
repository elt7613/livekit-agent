import asyncio

from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def main():
  livekit_api = api.LiveKitAPI()

  trunk = api.SIPInboundTrunkInfo(
    name = "My trunk",
    numbers = ["+19387585572"],
    krisp_enabled = True,
  )

  request = api.CreateSIPInboundTrunkRequest(
    trunk = trunk
  )

  trunk = await livekit_api.sip.create_sip_inbound_trunk(request)
  print(trunk)

  await livekit_api.aclose()

asyncio.run(main())

trunk_id = "ST_aArEp7NkAGXe"