import logging
import time
from opentelemetry import trace

logger = logging.getLogger("calling-agent")


class AgentEventTracker:
    """Centralized event tracking for agent activities"""
    
    def __init__(self, agent_setup):
        self.agent_setup = agent_setup
        self.tracer = trace.get_tracer("livekit-agent")
    
    def _create_event_span(self, event_name, additional_attrs=None):
        """Helper method to create event spans with common Langfuse attributes"""
        if not self.agent_setup.session_manager:
            return None
            
        try:
            # Create as child of root session span when available
            ctx = self.agent_setup.session_manager.get_root_context()
            span = self.tracer.start_span(event_name, context=ctx) if ctx else self.tracer.start_span(event_name)
            
            # Set common Langfuse attributes
            self.agent_setup.session_manager.ensure_trace_linked(span)
            span.set_attribute("langfuse.observation.type", "event")
            
            # Add additional attributes
            if additional_attrs:
                for key, value in additional_attrs.items():
                    if value is not None:
                        span.set_attribute(key, str(value))
            
            return span
        except Exception as e:
            logger.error(f"Failed to create event span '{event_name}': {e}")
            return None
    
    def track_function_calls_finished(self, ctx):
        """Track when function calls are finished"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            span = self._create_event_span("function_calls_finished", {
                "event_name": "function_calls_finished",
                "conversation_turn": self.agent_setup.conversation_turn_count
            })
            
            if span:
                # Track function call completion
                self.agent_setup.session_manager.track_user_action(
                    "function_calls_completed",
                    turn_number=self.agent_setup.conversation_turn_count,
                    timestamp=time.time()
                )
                span.end()
                
        except Exception as e:
            logger.error(f"Error tracking function calls finished: {e}")
    
    def track_before_llm_call(self, ctx):
        """Track before LLM call event"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            # Increment conversation turn count
            self.agent_setup.conversation_turn_count += 1
            
            # Track conversation turn (avoid creating span for better performance)
            self.agent_setup.session_manager.track_user_action(
                "conversation_turn_started",
                turn_number=self.agent_setup.conversation_turn_count,
                timestamp=time.time()
            )
                
        except Exception as e:
            logger.error(f"Error tracking before LLM call: {e}")
    
    def track_after_llm_call(self, ctx):
        """Track after LLM call event"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            # Track conversation turn completion (avoid creating span for better performance)
            self.agent_setup.session_manager.track_user_action(
                "conversation_turn_completed",
                turn_number=self.agent_setup.conversation_turn_count,
                timestamp=time.time()
            )
                
        except Exception as e:
            logger.error(f"Error tracking after LLM call: {e}")
    
    def track_user_speech_committed(self, message):
        """Track when user speech is committed/finalized"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            # Track user speech (avoid creating span for better performance)
            self.agent_setup.session_manager.track_user_action(
                "user_speech_received",
                content_length=len(message.content),
                turn_number=self.agent_setup.conversation_turn_count,
                timestamp=time.time()
            )
                
        except Exception as e:
            logger.error(f"Error tracking user speech committed: {e}")
    
    def track_agent_speech_committed(self, message):
        """Track when agent speech is committed/finalized"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            message_content = getattr(message, 'content', str(message))
            
            # Track agent speech (avoid creating span for better performance)
            self.agent_setup.session_manager.track_user_action(
                "agent_speech_sent",
                content_length=len(message_content),
                turn_number=self.agent_setup.conversation_turn_count,
                timestamp=time.time()
            )
                
        except Exception as e:
            logger.error(f"Error tracking agent speech committed: {e}")
    
    def track_room_entry(self):
        """Track agent room entry event (non-blocking)"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            # Track room entry as event instead of span for better performance
            self.agent_setup.session_manager.add_user_event(
                "agent_joined_room",
                room_name=self.agent_setup.room_name,
                timestamp=time.time()
            )
                
        except Exception as e:
            logger.error(f"Error tracking room entry: {e}")
    
    def track_greeting_sent(self, greeting_instructions):
        """Track initial greeting sent to user (non-blocking)"""
        if not self.agent_setup.session_manager:
            return None
            
        try:
            # Track greeting as event instead of span for better performance
            self.agent_setup.session_manager.add_user_event(
                "received_greeting",
                greeting_type="initial",
                timestamp=time.time()
            )
            
            return None
            
        except Exception as e:
            logger.error(f"Error tracking greeting: {e}")
            return None
    
    def track_room_exit(self):
        """Track agent room exit event"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            # Track user's session end (avoid creating span for better performance)
            self.agent_setup.session_manager.track_user_action(
                "session_ended",
                conversation_turns=self.agent_setup.conversation_turn_count,
                timestamp=time.time()
            )
                
        except Exception as e:
            logger.error(f"Error tracking room exit: {e}")
    
    def track_recording_event(self, event_type, **metadata):
        """Track recording-related events"""
        if not self.agent_setup.session_manager:
            return
            
        try:
            # Track recording event (avoid creating span for better performance)
            self.agent_setup.session_manager.track_user_action(
                f"recording_{event_type}",
                timestamp=time.time(),
                **metadata
            )
                
        except Exception as e:
            logger.error(f"Error tracking recording event '{event_type}': {e}")


def create_event_tracker(agent_setup):
    """Factory function to create an event tracker instance"""
    return AgentEventTracker(agent_setup)
