import logging
from dotenv import load_dotenv
from livekit import api
from livekit.agents import get_job_context,RunContext,function_tool
from .call_recording import CallRecording
from .call_metadata import CallMetadata
from opentelemetry import trace
import asyncio

load_dotenv()

# Set up logging with console handler
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calling-agent")


class HangupCall(CallRecording,CallMetadata):
    def __init__(self, response, config) -> None:
        # Initialize parent classes
        CallRecording.__init__(self)
        CallMetadata.__init__(self, config)
        
        self.response = response
        self.session_manager = None  # Will be set by AgentSetup
        
    def set_session_manager(self, session_manager):
        """Set the session manager for tracing"""
        self.session_manager = session_manager
        
    async def hangup_call(self):
        ctx = get_job_context()
        if ctx is None:
            return
        
        # Trace call hangup
        if self.session_manager:
            tracer = trace.get_tracer("livekit-agent")
            otel_ctx = self.session_manager.get_root_context()
            with tracer.start_as_current_span("call_hangup", context=otel_ctx) as span:
                self.session_manager.ensure_trace_linked(span)
                span.set_attribute("langfuse.observation.type", "event")
                span.set_attribute("event_name", "call_hangup")
                span.set_attribute("room_name", ctx.room.name)
        
        # Add a short delay to allow pending messages to process
        await asyncio.sleep(0.2)  # Reduced from 1 second for faster call termination
        
        # Existing code
        if self.is_recording:
            try:
                self.response = await self._stop_recording_internal()
                
                if self.session_manager:
                    self.session_manager.add_event("recording_stopped",
                                                  has_response=bool(self.response))
            except Exception as e:
                logger.error(f"Error stopping recording: {e}")
                if self.session_manager:
                    self.session_manager.add_event("recording_stop_error",
                                                  error_message=str(e))
        
        await self.save_call_metadata(self.response)
        # End tracing session BEFORE room deletion to ensure spans are exported even if process exits
        if self.session_manager:
            try:
                self.session_manager.end_session(
                    end_time=asyncio.get_event_loop().time(),
                    final_status="hangup_user",
                    user_id=self.session_manager.user_id,
                    total_user_interactions=self.session_manager.conversation_count,
                )
            except Exception as e:
                logger.warning(f"end_session during user hangup failed: {e}")
        await ctx.api.room.delete_room(api.DeleteRoomRequest(room=ctx.room.name))
    
    async def handle_unanswered_call(self, reason="not_answered"):
        """Handle calls that are not picked up or fail to connect"""
        logger.info(f"Handling unanswered call with reason: {reason}")
        
        # Trace unanswered call
        if self.session_manager:
            tracer = trace.get_tracer("livekit-agent")
            otel_ctx = self.session_manager.get_root_context()
            with tracer.start_as_current_span("unanswered_call", context=otel_ctx) as span:
                self.session_manager.ensure_trace_linked(span)
                span.set_attribute("langfuse.observation.type", "event")
                span.set_attribute("event_name", "unanswered_call")
                span.set_attribute("unanswered_reason", reason)
        
        # Stop any recording if it was started
        if self.is_recording:
            try:
                await self._stop_recording_internal()
                logger.info("Stopped recording for unanswered call")
                
                if self.session_manager:
                    self.session_manager.add_event("recording_stopped_unanswered",
                                                  reason=reason)
            except Exception as e:
                logger.error(f"Error stopping recording for unanswered call: {e}")
                if self.session_manager:
                    self.session_manager.add_event("recording_stop_error_unanswered",
                                                  error_message=str(e),
                                                  reason=reason)
        
        # Save metadata for unanswered call
        await self.save_unanswered_call_metadata(reason)
        
        # Clean up the room
        try:
            ctx = get_job_context()
            if ctx and ctx.api:
                # End tracing session BEFORE room deletion to ensure export
                if self.session_manager:
                    try:
                        self.session_manager.end_session(
                            end_time=asyncio.get_event_loop().time(),
                            final_status="unanswered",
                            unanswered_reason=reason,
                            user_id=self.session_manager.user_id,
                            total_user_interactions=self.session_manager.conversation_count,
                        )
                    except Exception as e:
                        logger.warning(f"end_session during unanswered flow failed: {e}")
                await ctx.api.room.delete_room(api.DeleteRoomRequest(room=ctx.room.name))
                logger.info(f"Room {ctx.room.name} deleted after unanswered call")
                
                if self.session_manager:
                    self.session_manager.add_event("room_deleted",
                                                  room_name=ctx.room.name,
                                                  reason="unanswered_call")
        except Exception as e:
            logger.error(f"Error deleting room after unanswered call: {e}")
            if self.session_manager:
                self.session_manager.add_event("room_deletion_error",
                                              error_message=str(e))

    @function_tool()
    async def end_call(self, ctx: RunContext):
        """Called when hangingup the call is required."""
        logger.info("ending the call")
        
        # Trace function call
        if self.session_manager:
            tracer = trace.get_tracer("livekit-agent")
            otel_ctx = self.session_manager.get_root_context()
            with tracer.start_as_current_span("end_call_function", context=otel_ctx) as span:
                self.session_manager.ensure_trace_linked(span)
                span.set_attribute("langfuse.observation.type", "event")
                span.set_attribute("event_name", "end_call_function_called")
        
        # let the agent finish speaking
        await ctx.wait_for_playout()

        # Stop recording and capture response if recording is active
        if self.is_recording:
            try:
                self.response = await self._stop_recording_internal()
                logger.info(f"Stopped recording before ending call. Response: {self.response}")
                
                if self.session_manager:
                    self.session_manager.add_event("recording_stopped_end_call",
                                                  has_response=bool(self.response),
                                                  response_preview=str(self.response)[:100] if self.response else None)
            except Exception as e:
                logger.error(f"Error stopping recording before ending call: {e}")
                self.response = None
                
                if self.session_manager:
                    self.session_manager.add_event("recording_stop_error_end_call",
                                                  error_message=str(e))
        
        await self.save_call_metadata(self.response)
        
        await self.hangup_call()