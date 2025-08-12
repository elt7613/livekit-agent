from livekit.agents import JobContext, WorkerOptions, cli, WorkerType, JobExecutorType
from livekit.agents.voice import AgentSession
from agent.agent_setup import AgentSetup
import logging, json, asyncio
from dotenv import load_dotenv
from utils.langfuse.langfuse_manager import LangfuseSessionManager
from utils.langfuse.langfuse_setup import setup_langfuse
from utils.extract_user_info import extract_user_info_from_metadata

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calling-agent")

# Suppress MongoDB DEBUG logs
logging.getLogger("pymongo").setLevel(logging.WARNING)

# Call monitring
async def monitor_sip_call_status(ctx: JobContext, agent_setup: AgentSetup, session_manager: LangfuseSessionManager = None):
    """Monitor SIP call status and handle unanswered calls with user tracking"""
    logger.info("Starting SIP call status monitoring...")
    
    monitoring_span = None
    if session_manager:
        monitoring_span = session_manager.create_child_span(
            "sip_call_monitoring",
            **{
                "langfuse.observation.type": "span",
                "monitoring.timeout_seconds": 15,
                "event_name": "sip_monitoring"
            }
        )
    
    # Wait for SIP participant to join or timeout
    timeout_seconds = 15  
    start_time = asyncio.get_event_loop().time()
    
    try:
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time
            
            # Check if timeout reached
            if elapsed > timeout_seconds:
                if session_manager:
                    session_manager.add_user_event(
                        "call_timeout", 
                        elapsed_seconds=elapsed,
                        timeout_reason="no_answer"
                    )
                    session_manager.track_user_action(
                        "call_missed", 
                        duration=elapsed,
                        reason="timeout"
                    )
                await agent_setup.handle_unanswered_call()
                return False
            
            # Check for SIP participants
            if ctx.room.remote_participants:
                for participant in ctx.room.remote_participants.values():
                    sip_status = participant.attributes.get("sip.callStatus")
                    
                    if sip_status == "active":
                        # Update inbound numbers when we first see an active SIP participant
                        attrs = getattr(participant, "attributes", {}) or {}
                        caller_number = attrs.get("sip.phoneNumber") or participant.identity

                        if hasattr(agent_setup, 'update_inbound_phone_numbers'):
                            agent_setup.update_inbound_phone_numbers(caller_number)

                        if session_manager:
                            session_manager.add_user_event(
                                "call_answered", 
                                participant_id=participant.identity,
                                elapsed_seconds=elapsed,
                                call_status="active"
                            )
                            session_manager.track_user_action(
                                "call_answered",
                                participant_id=participant.identity,
                                answer_time=elapsed
                            )
                        return True
                    elif sip_status == "hangup":
                        if session_manager:
                            session_manager.add_user_event(
                                "call_hangup", 
                                participant_id=participant.identity,
                                elapsed_seconds=elapsed,
                                call_status="hangup"
                            )
                            session_manager.track_user_action(
                                "call_hungup",
                                participant_id=participant.identity,
                                duration=elapsed
                            )
                        await agent_setup.handle_unanswered_call()
                        return False
            
            await asyncio.sleep(0.1)  
    finally:
        if monitoring_span:
            monitoring_span.end()


async def entrypoint(ctx: JobContext):    
    agent_setup = None
    session_manager = None
    
    try:
        # Setup Langfuse tracing first
        setup_success = await setup_langfuse()
        if not setup_success:
            logger.warning("Langfuse setup failed, continuing without tracing")
        
        # Parse metadata and extract user information
        metadata = json.loads(ctx.job.metadata)

        if "agent_config" in metadata:
            is_inbound_call = False
            agent_config = metadata.get("agent_config", {})
            logger.info("Detected outbound call based on agent_config key")
        else:
            is_inbound_call = True
            agent_config = metadata
            logger.info("Detected inbound call based on missing agent_config key")
        
        logger.info(f"Call type detected: {'inbound' if is_inbound_call else 'outbound'}")

        # Extract user information from metadata
        user_identifier, user_metadata = await extract_user_info_from_metadata(agent_config)
        
        # Create session manager with user tracking
        session_manager = LangfuseSessionManager(
            room_name=ctx.room.name,
            user_identifier=user_identifier,
            user_metadata=user_metadata
        )
        
        session_success = session_manager.setup_session_tracing()
        
        if session_success:
            # Prepare session metadata, avoiding conflicts
            session_metadata = {
                "agent_type": "voice_assistant",
                "start_time": asyncio.get_event_loop().time(),
                "call_type": "inbound" if is_inbound_call else "outbound",
            }
            
            # Add agent config metadata, but avoid conflicts with existing keys
            for key, value in agent_config.items():
                if key not in session_metadata and key != "agent_name":  # Avoid conflict
                    session_metadata[key] = value
            
            # Add agent_name separately to avoid conflict
            session_metadata["configured_agent_name"] = agent_config.get("agent_name", "BLACKDWARF-Agnet")
            
            # Start the main session span with user context
            session_manager.start_session(**session_metadata)
        
        #logger.info(f"ROOM NAME: {agent_config.get('room_name')}")
        logger.info(f"USER ID: {session_manager.user_id}")
        logger.info(f"CALL TYPE: {'inbound' if is_inbound_call else 'outbound'}")
        logger.info(f"Room Info: {ctx.room}")
        
        # Initialize agent setup
        agent_setup = AgentSetup(config=agent_config, room=ctx.room)
        
        # Set the session manager in agent_setup for integration
        if session_manager and hasattr(agent_setup, 'set_session_manager'):
            agent_setup.set_session_manager(session_manager)
        
        ai_components = await agent_setup.get_ai_components()
        
        session = AgentSession(
            llm=ai_components["llm"],
            tts=ai_components["tts"],
            stt=ai_components["stt"],
            vad=ai_components["vad"],
            turn_detection=ai_components["turn_detection"],
            min_endpointing_delay=0.1,  
            max_endpointing_delay=1.5,  
            allow_interruptions=True,
            min_interruption_duration=0.25,  
        )
        
        await ctx.connect()
        logger.info(f"Connected to room: {ctx.room.name}")
        
        if session_manager:
            session_manager.add_user_event(
                "room_connected", 
                room_name=ctx.room.name,
                connection_time=asyncio.get_event_loop().time()
            )
            session_manager.track_user_action(
                "room_joined",
                room_name=ctx.room.name,
                timestamp=asyncio.get_event_loop().time()
            )

        await session.start(
            room=ctx.room,
            agent=agent_setup
        )
        logger.info("Agent session started successfully.")
        
        if session_manager:
            session_manager.add_user_event(
                "agent_session_started",
                session_start_time=asyncio.get_event_loop().time()
            )
            session_manager.track_user_action(
                "conversation_started",
                timestamp=asyncio.get_event_loop().time()
            )
        
        # Monitor SIP call status with session and user tracking
        call_result = await monitor_sip_call_status(ctx, agent_setup, session_manager)
        
        if session_manager:
            final_action = "call_completed_successfully" if call_result else "call_failed"
            session_manager.add_user_event(
                "call_completed", 
                call_answered=call_result,
                end_time=asyncio.get_event_loop().time(),
                total_turns=session_manager.conversation_count
            )
            session_manager.track_user_action(
                final_action,
                call_answered=call_result,
                duration=asyncio.get_event_loop().time(),
                total_turns=session_manager.conversation_count
            )

    except Exception as e:
        logger.error(f"Error in entrypoint: {e}")
        
        if session_manager:
            session_manager.add_user_event(
                "error", 
                error_message=str(e),
                error_time=asyncio.get_event_loop().time(),
                error_type="entrypoint_error"
            )
            session_manager.track_user_action(
                "error_occurred",
                error_message=str(e),
                error_type="entrypoint_error",
                timestamp=asyncio.get_event_loop().time()
            )
        
        if agent_setup:
            try:
                await agent_setup.handle_unanswered_call()
            except Exception as meta_error:
                logger.error(f"Error saving metadata for failed call: {meta_error}")
    finally:
        # End the session with user summary
        if session_manager:
            session_manager.end_session(
                end_time=asyncio.get_event_loop().time(),
                final_status="completed",
                user_id=session_manager.user_id,
                total_user_interactions=session_manager.conversation_count
            )
        
        logger.info("Agent session ended.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="Calling-Agent-System", 
        worker_type=WorkerType.ROOM,
        job_executor_type=JobExecutorType.PROCESS,
        job_memory_warn_mb=700,  
        job_memory_limit_mb=1000,  
    ))