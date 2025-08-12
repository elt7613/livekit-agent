import hashlib,logging
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry import context as context_api
from langfuse import get_client

load_dotenv()

logger = logging.getLogger("calling-agent")


class LangfuseSessionManager:
    """
    Enhanced Langfuse session manager with proper conversation and user tracking
    """
    def __init__(self, room_name: str, user_identifier: str = None, user_metadata: dict = None):
        self.session_id = room_name
        self.room_name = room_name
        self.user_id = self._generate_user_id(user_identifier)
        self.user_metadata = user_metadata or {}
        self.tracer = None
        self.root_span = None
        self.conversation_count = 0
        self._ended = False
        self._ctx_token = None
        
    def _generate_user_id(self, user_identifier: str = None) -> str:
        """
        Generate a consistent user ID from various possible identifiers
        """
        if user_identifier:
            # If a specific user identifier is provided, use it
            return user_identifier
        
        # Try to extract user info from room name or other sources
        # For SIP calls, we might have phone numbers or other identifiers
        if self.room_name:
            # Create a hash-based user ID from room name for consistency
            # This ensures the same caller gets the same user ID across sessions
            hash_object = hashlib.sha256(self.room_name.encode())
            return f"user_{hash_object.hexdigest()[:8]}"
        
        # Fallback to a generic user ID
        return "anonymous_user"
    
    def set_user_metadata(self, **metadata):
        """
        Set additional user metadata that will be attached to all spans
        """
        self.user_metadata.update(metadata)
        
    def setup_session_tracing(self) -> bool:
        """
        Setup OpenTelemetry tracing with session-specific attributes
        """
        try:
            # Get the global tracer
            self.tracer = trace.get_tracer("livekit-calling-agent")
            
            logger.info(f"Session tracing setup completed for session: {self.session_id}, user: {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup session tracing: {e}")
            return False
    
    def get_root_context(self):
        """
        Return an OTEL context that has the session root span set as current.
        Useful to ensure new spans belong to the same trace.
        """
        if self.root_span:
            return trace.set_span_in_context(self.root_span)
        return None
    
    def ensure_trace_linked(self, span=None):
        """
        Ensure the provided span (or root span) has langfuse user/session linking
        attributes so all observations are associated correctly.
        """
        target_span = span or self.root_span
        if target_span is None:
            return
        try:
            target_span.set_attribute("langfuse.session.id", self.session_id)
            target_span.set_attribute("langfuse.user.id", self.user_id)
        except Exception as e:
            logger.error(f"Failed to set trace linking attributes: {e}")
    
    def get_trace_id_hex(self, span=None) -> str | None:
        """
        Return the hex-encoded trace ID for the given span (or root span).
        Helpful for verifying linkage in Langfuse UI.
        """
        target_span = span or self.root_span
        if target_span is None:
            return None
        try:
            sc = target_span.get_span_context()
            trace_id = getattr(sc, "trace_id", 0)
            if not trace_id:
                return None
            return f"{trace_id:032x}"
        except Exception as e:
            logger.error(f"Failed to read trace id: {e}")
            return None
    
    def start_session(self, **metadata):
        """
        Start the main session span that will group all other spans with user tracking
        """
        if not self.tracer:
            return None
            
        try:
            # Create the root span for the entire session
            self.root_span = self.tracer.start_span(f"LiveKit_Voice_Call_{self.session_id}")

            # Attach root span as current so child spans across the app join the SAME trace
            try:
                self._ctx_token = context_api.attach(trace.set_span_in_context(self.root_span))
            except Exception as att_err:
                logger.warning(f"Failed to attach root span to context: {att_err}")
            
            # Set required Langfuse session attributes
            self.root_span.set_attribute("langfuse.session.id", self.session_id)
            self.root_span.set_attribute("langfuse.user.id", self.user_id)
            self.root_span.set_attribute("langfuse.trace.name", f"LiveKit Call - {self.room_name}")
            self.root_span.set_attribute("langfuse.observation.type", "span")
            
            # Set LiveKit specific attributes
            self.root_span.set_attribute("livekit.room.name", self.room_name)
            self.root_span.set_attribute("livekit.session.type", "voice_call")
            
            # Add user metadata
            for key, value in self.user_metadata.items():
                self.root_span.set_attribute(f"langfuse.user.metadata.{key}", str(value))
            
            # Add any additional metadata
            for key, value in metadata.items():
                self.root_span.set_attribute(f"langfuse.trace.metadata.{key}", str(value))
            
            # Attach and log trace id for verification
            # Compute trace id for verification logs (not added as attribute)
            trace_id_hex = self.get_trace_id_hex(self.root_span) or "unknown"

            # Also set Langfuse top-level user/session on the trace via SDK (v3)
            # This populates the UI 'User' and 'Session' fields, not just attributes.
            try:
                with trace.use_span(self.root_span, end_on_exit=False):
                    client = get_client()
                    client.update_current_trace(
                        user_id=self.user_id,
                        session_id=self.session_id,
                        tags=["livekit", "voice_call"],
                    )
            except Exception as lf_err:
                logger.warning(f"Langfuse SDK update_current_trace failed: {lf_err}")
            
            logger.info(f"Langfuse session started: {self.session_id} for user: {self.user_id} trace_id={trace_id_hex}")
            return self.root_span
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return None
    
    def create_child_span(self, span_name: str, **attributes):
        """
        Create a child span within the session with proper user context
        """
        if not self.tracer or not self.root_span:
            return None
            
        try:
            # Create child span with the root span as parent context
            ctx = trace.set_span_in_context(self.root_span)
            span = self.tracer.start_span(span_name, context=ctx)
            
            # Inherit session and user ID from parent
            self.ensure_trace_linked(span)
            
            # Set any additional attributes
            for key, value in attributes.items():
                if value is not None:  # Skip None values
                    span.set_attribute(key, str(value))
                        
            return span
        except Exception as e:
            logger.error(f"Failed to create child span '{span_name}': {e}")
            return None
    
    def create_conversation_span(self, turn_number: int, user_input: str = None, agent_response: str = None):
        """
        Create a span specifically for conversation turns with user tracking
        """
        if not self.tracer or not self.root_span:
            return None
            
        try:
            ctx = trace.set_span_in_context(self.root_span)
            span = self.tracer.start_span(f"conversation_turn_{turn_number}", context=ctx)
            
            # Set conversation-specific attributes
            self.ensure_trace_linked(span)
            span.set_attribute("langfuse.observation.type", "span")
            span.set_attribute("conversation.turn_number", turn_number)
            
            if user_input:
                span.set_attribute("langfuse.observation.input", user_input[:500])
                span.set_attribute("conversation.user_input", user_input[:500])
                
            if agent_response:
                span.set_attribute("langfuse.observation.output", agent_response[:500])
                span.set_attribute("conversation.agent_response", agent_response[:500])
            
            return span
        except Exception as e:
            logger.error(f"Failed to create conversation span: {e}")
            return None
    
    def add_user_event(self, event_name: str, **attributes):
        """
        Add a user-specific event to the current session
        """
        if not self.root_span:
            return
            
        try:
            # Add event to the root span with user context
            event_attributes = {
                "user_id": self.user_id,
                "session_id": self.session_id,
                # Also include Langfuse-mapped keys to maximize linkage in UI
                "langfuse.user.id": self.user_id,
                "langfuse.session.id": self.session_id,
            }
            
            for key, value in attributes.items():
                if value is not None:
                    event_attributes[key] = str(value)
                    
            self.root_span.add_event(event_name, attributes=event_attributes)
        except Exception as e:
            logger.error(f"Failed to add user event '{event_name}': {e}")
    
    def add_event(self, event_name: str, **attributes):
        """
        Add an event to the current session (maintains backward compatibility)
        """
        self.add_user_event(event_name, **attributes)
    
    def track_user_action(self, action_type: str, **action_data):
        """
        Track specific user actions with dedicated spans (non-blocking for critical path)
        """
        if not self.tracer or not self.root_span:
            return None
            
        try:
            # For critical path operations, just add events instead of creating spans
            # This prevents blocking during call startup
            event_attributes = {
                "action.type": action_type,
                "langfuse.session.id": self.session_id,
                "langfuse.user.id": self.user_id,
                "langfuse.observation.type": "event"
            }
            
            # Add action-specific data
            for key, value in action_data.items():
                if value is not None:
                    event_attributes[f"action.{key}"] = str(value)
            
            # Add event to root span instead of creating new span
            self.root_span.add_event(f"user_action_{action_type}", attributes=event_attributes)
            return None
        except Exception as e:
            logger.error(f"Failed to track user action '{action_type}': {e}")
            return None
    
    def increment_conversation_count(self):
        """Increment and return conversation count"""
        self.conversation_count += 1
        return self.conversation_count
    
    def end_session(self, **final_metadata):
        """
        End the session span with user summary
        """
        if self._ended or not self.root_span:
            return
            
        try:
            self._ended = True
            # Add final metadata
            for key, value in final_metadata.items():
                if value is not None:
                    self.root_span.set_attribute(f"langfuse.trace.metadata.{key}", str(value))
            
            # Add conversation and user summary
            self.root_span.set_attribute("langfuse.trace.metadata.total_conversation_turns", 
                                       self.conversation_count)
            # Use a simple completed status for final trace metadata
            self.root_span.set_attribute("langfuse.trace.metadata.status", "completed")
            self.root_span.set_attribute("langfuse.trace.metadata.user_id", self.user_id)
            
            # Compute trace id for final log visibility (not added as attribute)
            trace_id_hex = self.get_trace_id_hex(self.root_span) or "unknown"

            # Ensure top-level user/session are set on the trace via Langfuse SDK as well
            try:
                with trace.use_span(self.root_span, end_on_exit=False):
                    client = get_client()
                    client.update_current_trace(
                        user_id=self.user_id,
                        session_id=self.session_id,
                    )
                    # Best-effort flush of SDK buffers (non-OTEL) in short-lived flows
                    client.flush()
            except Exception as lf_err:
                logger.warning(f"Langfuse SDK update/flush at end_session failed: {lf_err}")
            
            # End the span
            self.root_span.end()
            logger.info(f"Langfuse session ended: {self.session_id} for user: {self.user_id} with {self.conversation_count} turns trace_id={trace_id_hex}")

            # Best-effort flush so spans are not lost on quick shutdown (e.g., user hangup)
            try:
                provider = trace.get_tracer_provider()
                if hasattr(provider, "force_flush"):
                    provider.force_flush(timeout_millis=1500)
            except Exception as fe:
                logger.warning(f"Tracing force_flush failed: {fe}")
            finally:
                # Detach root span from current context
                try:
                    if self._ctx_token is not None:
                        context_api.detach(self._ctx_token)
                        self._ctx_token = None
                except Exception as det_err:
                    logger.warning(f"Failed to detach root span context: {det_err}")
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

