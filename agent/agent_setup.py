import logging
import os
import asyncio
from dotenv import load_dotenv
from livekit.agents.voice import Agent
from agent.utils.hangup_call import HangupCall
from agent.config.get_system_prompt import get_system_prompt
from agent.config.get_tools import get_tools
from livekit import rtc
from agent.utils.conversation_history import ConversationHistory
from livekit.agents import ChatContext, RunContext
from agent.utils import create_tracked_components, create_event_tracker
from tools.date_time import get_date
import uuid

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calling-agent")

class AgentSetup(Agent, HangupCall, ConversationHistory):
    def __init__(self, config: dict, room: rtc.Room = None) -> None:
        self.config = config
        self.user_id = config.get("user_id")
        self.workflow_id = config.get("workflow_id")
        self.call_id = config.get("call_id",None)
        self.system_agent_name = config.get("system_agent_name")
        self.custom_instructions = config.get("custom_instructions")
        self.agent_language = config.get("agent_language")
        self.agent_name = config.get("agent_name")
        self.agent_gender = config.get("agent_gender")
        self.room_name = config.get("room_name")
        self.voice_id = config.get("voice_id")
        self.language_tts = config.get("language_tts")
        self.company_name = config.get("company_name")
        self.individual_name = config.get("individual_name")
        self.knowledge_base = config.get("knowledge_base")
        self.llm_model = config.get("llm_model")
        self.stt_model = config.get("stt_model")
        self.tts_model = config.get("tts_model")

        if not self.call_id:
            self.call_id = str(uuid.uuid4()) 
            self.config["call_id"] = self.call_id
        
        # Call tracking 
        self.call_start_time = None
        self.call_answered = False
        self._greeting_sent = False 
        self.session_manager = None
        self.conversation_turn_count = 0
        
        # Environment variables 
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
        self.openrouter_base_url = os.environ.get("OPENROUTER_BASE_URL")
        
        # Instructions and tools
        try:
            instructions = get_system_prompt(
                workflow_id=self.workflow_id,
                system_agent_name=self.system_agent_name,
                custom_instructions=self.custom_instructions,
                agent_language=self.agent_language,
                agent_gender=self.agent_gender,
                company_name=self.company_name,
                individual_name=self.individual_name,
                agent_name=self.agent_name,
                knowledge_base=self.knowledge_base
            )
            tools = get_tools(self.system_agent_name)
        except Exception as e:
            logger.error(f"Error during initialization setup: {e}")
            # Fallback to basic configuration
            instructions = f"You are {self.agent_name}, a helpful assistant."
            tools = []

        current_date = get_date()
        
        # Initialize the ChatContext
        self.initial_ctx = ChatContext()
        self.initial_ctx.add_message(role="assistant", content=f"# Workflow ID: {self.workflow_id}, # Today's Date: {current_date}")

        # Initializing the Agent parent class with instructions and tools
        Agent.__init__(self, instructions=instructions, chat_ctx=self.initial_ctx, tools=tools)
        
        # Initialize response variable
        self.response = None
        
        # Initialize event tracker for Langfuse tracking
        self.event_tracker = create_event_tracker(self)
        
        # Initialize other parent classes 
        HangupCall.__init__(self, self.response, self.config)
        ConversationHistory.__init__(self, room, self.user_id, self.workflow_id, self.call_id)
        
        logger.info(f"AgentSetup initialized for agent: {self.agent_name}")

    async def get_ai_components(self):
        """Initialize AI components with proper user and session tracing hooks"""
        return create_tracked_components(self)

    def set_session_manager(self, session_manager):
        """Set the Langfuse session manager for this agent"""
        self.session_manager = session_manager
        logger.info(f"Session manager set for user: {session_manager.user_id}")
    
    # Override Agent methods to capture conversation events with user tracking
    async def on_function_calls_finished(self, ctx: RunContext):
        """Called when function calls are finished - capture tool usage with user context"""
        self.event_tracker.track_function_calls_finished(ctx)
        return await super().on_function_calls_finished(ctx)
    
    async def on_before_llm_call(self, ctx: RunContext):
        """Called before LLM call - capture conversation context with user tracking"""
        self.event_tracker.track_before_llm_call(ctx)
        return await super().on_before_llm_call(ctx)
    
    async def on_after_llm_call(self, ctx: RunContext):
        """Called after LLM call - capture response with user tracking"""
        self.event_tracker.track_after_llm_call(ctx)
        return await super().on_after_llm_call(ctx)
    
    async def on_user_speech_committed(self, message):
        """Called when user speech is committed/finalized with user tracking"""
        self.event_tracker.track_user_speech_committed(message)
        
        # Call the original method if it exists
        if hasattr(super(), 'on_user_speech_committed'):
            await super().on_user_speech_committed(message)
    
    async def on_agent_speech_committed(self, message):
        """Called when agent speech is committed/finalized with user tracking"""  
        self.event_tracker.track_agent_speech_committed(message)
        
        # Call the original method if it exists
        if hasattr(super(), 'on_agent_speech_committed'):
            await super().on_agent_speech_committed(message)

    # Agent lifecycle with user tracking
    async def on_enter(self):
        """Optimized room entry with concurrent operations and user tracking"""
        logger.info("Agent entering room...")
        
        # Track room entry event
        self.event_tracker.track_room_entry()
        
        async def setup_recording():
            try:
                # Minimal delay for room stability
                await asyncio.sleep(0.5)  # Reduced from 1 second
                await self._start_recording_internal()
                logger.info("Recording started")
                
                if self.session_manager:
                    self.event_tracker.track_recording_event("started")
            except Exception as e:
                logger.error(f"Recording setup error: {e}")
        
        async def setup_monitoring():
            try:
                await self.setup_conversation_monitoring(self.session)
                logger.info("Conversation monitoring setup")
            except Exception as e:
                logger.error(f"Monitoring setup error: {e}")
        
        async def send_greeting():
            try:
                if not self._greeting_sent:
                    greeting_instructions = f"Greet and introduce yourself briefly."
                    
                    # Capture greeting in Langfuse with user context
                    if self.session_manager:
                        span = self.event_tracker.track_greeting_sent(greeting_instructions)
                        try:
                            await self.session.generate_reply(
                                instructions=greeting_instructions,
                                allow_interruptions=True
                            )
                        finally:
                            if span:
                                span.end()
                    else:
                        await self.session.generate_reply(
                            instructions=greeting_instructions,
                            allow_interruptions=True
                        )
                    
                    self._greeting_sent = True
                    logger.info("Greeting sent")
            except Exception as e:
                logger.error(f"Greeting error: {e}")
        
        # Execute all setup tasks concurrently 
        await asyncio.gather(
            setup_recording(),
            setup_monitoring(),
            send_greeting(),
            return_exceptions=True 
        )
        logger.info("Room entry completed")

    async def on_exit(self):
        """Called when the agent exits the room with user tracking"""
        logger.info("Agent exiting room...")
        
        # Track room exit event
        self.event_tracker.track_room_exit()

        # Stop recording and capture response if recording is active
        if self.is_recording:
            try:
                self.response = await self._stop_recording_internal()
                logger.info(f"Stopped recording before ending call. Response: {self.response}")
                
                if self.session_manager:
                    self.event_tracker.track_recording_event("stopped", has_response=bool(self.response))
            except Exception as e:
                logger.error(f"Error stopping recording before ending call: {e}")
                self.response = None

        await self.save_call_metadata(self.response)
        await self._save_conversation()