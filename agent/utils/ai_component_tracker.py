import logging
from opentelemetry import trace
from livekit.plugins import openai, cartesia, deepgram, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("calling-agent")


class TrackedLLM(openai.LLM):
    """LLM wrapper with automatic Langfuse tracking"""
    
    def __init__(self, agent_setup, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_setup = agent_setup
        
    async def generate_response(self, prompt, **kwargs):
        """Override to capture LLM interactions with user tracking"""
        if self.agent_setup.session_manager:
            tracer = trace.get_tracer("livekit-agent")
            ctx = self.agent_setup.session_manager.get_root_context()
            with tracer.start_as_current_span("llm_generation", context=ctx) as span:
                self.agent_setup.session_manager.ensure_trace_linked(span)
                # Set Langfuse-specific attributes with user context
                self._set_langfuse_attributes(span, "generation", {
                    "langfuse.observation.model.name": self.agent_setup.llm_model,
                    "langfuse.observation.input": str(prompt)[:1000],
                    "component_type": "llm"
                })
                
                try:
                    response = await super().generate_response(prompt, **kwargs)
                    if response:
                        span.set_attribute("langfuse.observation.output", str(response)[:1000])
                        span.set_attribute("response_length", len(str(response)))
                    return response
                except Exception as e:
                    span.set_attribute("error", str(e))
                    span.set_attribute("status", "error")
                    raise
        else:
            return await super().generate_response(prompt, **kwargs)
    
    def _set_langfuse_attributes(self, span, observation_type, additional_attrs=None):
        """Helper method to set common Langfuse attributes"""
        if not self.agent_setup.session_manager:
            return
            
        self.agent_setup.session_manager.ensure_trace_linked(span)
        span.set_attribute("langfuse.observation.type", observation_type)
        
        if additional_attrs:
            for key, value in additional_attrs.items():
                if value is not None:
                    span.set_attribute(key, str(value))


class TrackedTTS(cartesia.TTS):
    """TTS wrapper with automatic Langfuse tracking"""
    
    def __init__(self, agent_setup, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_setup = agent_setup
        
    async def synthesize(self, text, **kwargs):
        """Override to capture TTS interactions with user context"""
        if self.agent_setup.session_manager:
            tracer = trace.get_tracer("livekit-agent")
            ctx = self.agent_setup.session_manager.get_root_context()
            with tracer.start_as_current_span("tts_synthesis", context=ctx) as span:
                self.agent_setup.session_manager.ensure_trace_linked(span)
                self._set_langfuse_attributes(span, "generation", {
                    "langfuse.observation.input": text[:500],
                    "component_type": "tts",
                    "voice_id": getattr(self.agent_setup, 'voice_id', 'unknown'),
                    "language": getattr(self.agent_setup, 'language_tts', 'unknown')
                })
                
                try:
                    result = await super().synthesize(text, **kwargs)
                    if result and hasattr(result, 'text'):
                        span.set_attribute("langfuse.observation.output", result.text[:500])
                    span.set_attribute("synthesis_success", True)
                    return result
                except Exception as e:
                    span.set_attribute("error", str(e))
                    span.set_attribute("synthesis_success", False)
                    raise
        else:
            return await super().synthesize(text, **kwargs)
    
    def _set_langfuse_attributes(self, span, observation_type, additional_attrs=None):
        """Helper method to set common Langfuse attributes"""
        if not self.agent_setup.session_manager:
            return
            
        span.set_attribute("langfuse.observation.type", observation_type)
        span.set_attribute("langfuse.session.id", self.agent_setup.session_manager.session_id)
        span.set_attribute("langfuse.user.id", self.agent_setup.session_manager.user_id)
        
        if additional_attrs:
            for key, value in additional_attrs.items():
                if value is not None:
                    span.set_attribute(key, str(value))


class TrackedSTT(deepgram.STT):
    """STT wrapper with automatic Langfuse tracking"""
    
    def __init__(self, agent_setup, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_setup = agent_setup
        
    async def recognize(self, buffer, **kwargs):
        """Override to capture STT interactions with user context"""
        if self.agent_setup.session_manager:
            tracer = trace.get_tracer("livekit-agent")
            ctx = self.agent_setup.session_manager.get_root_context()
            with tracer.start_as_current_span("stt_recognition", context=ctx) as span:
                self.agent_setup.session_manager.ensure_trace_linked(span)
                self._set_langfuse_attributes(span, "generation", {
                    "langfuse.observation.input": f"audio_buffer_len={len(buffer) if buffer else 0}",
                    "component_type": "stt",
                })
                span.set_attribute("language", getattr(self.agent_setup, 'agent_language', 'unknown'))
                
                try:
                    result = await super().recognize(buffer, **kwargs)
                    if result and hasattr(result, 'text'):
                        span.set_attribute("langfuse.observation.output", result.text[:500])
                        span.set_attribute("recognition_confidence", getattr(result, 'confidence', 0))
                    span.set_attribute("recognition_success", True)
                    return result
                except Exception as e:
                    span.set_attribute("error", str(e))
                    span.set_attribute("recognition_success", False)
                    raise
        else:
            return await super().recognize(buffer, **kwargs)
    
    def _set_langfuse_attributes(self, span, observation_type, additional_attrs=None):
        """Helper method to set common Langfuse attributes"""
        if not self.agent_setup.session_manager:
            return
            
        span.set_attribute("langfuse.observation.type", observation_type)
        span.set_attribute("langfuse.session.id", self.agent_setup.session_manager.session_id)
        span.set_attribute("langfuse.user.id", self.agent_setup.session_manager.user_id)
        
        if additional_attrs:
            for key, value in additional_attrs.items():
                if value is not None:
                    span.set_attribute(key, str(value))


def create_tracked_components(agent_setup):
    """Factory function to create tracked AI components"""
    try:
        # Create tracked LLM with optimized parameters for lower latency
        tracked_llm = TrackedLLM(
            agent_setup,
            model=agent_setup.llm_model,
            api_key=agent_setup.openrouter_api_key,
            base_url=agent_setup.openrouter_base_url,
            max_completion_tokens=120,
            temperature=0.3,
            timeout=15 
        )
        
        # Create tracked TTS with optimized parameters for faster delivery
        tracked_tts = TrackedTTS(
            agent_setup,
            model=agent_setup.tts_model,
            voice=agent_setup.voice_id,
            sample_rate=16000,
            language=agent_setup.language_tts 
        )
        
        # Create tracked STT with optimized parameters for lower latency
        tracked_stt = TrackedSTT(
            agent_setup,
            model=agent_setup.stt_model,
            interim_results=True,
            smart_format=True,
            punctuate=True,
            numerals=True,
            endpointing_ms=175,
            language="multi",
            filler_words=False,
            profanity_filter=False 
        )
        
        # Create VAD and turn detection (these don't need tracking)
        vad_instance = silero.VAD.load()
        turn_detector = MultilingualModel()
        
        logger.info("AI components created with Langfuse tracking")
        return {
            "llm": tracked_llm,
            "tts": tracked_tts,
            "stt": tracked_stt,
            "vad": vad_instance,
            "turn_detection": turn_detector
        }
        
    except Exception as e:
        logger.error(f"Error creating tracked AI components: {e}")
        # Fallback to untracked components
        llm = openai.LLM(
            model=agent_setup.llm_model,
            api_key=agent_setup.openrouter_api_key,
            base_url=agent_setup.openrouter_base_url,
            max_completion_tokens=120,
            temperature=0.3,
            timeout=15 
        )
        tts = cartesia.TTS(
            model=agent_setup.tts_model,
            voice=agent_setup.voice_id,
            sample_rate=16000,
            language=agent_setup.language_tts 
        )
        stt = deepgram.STT(
            model=agent_setup.stt_model,
            interim_results=True,
            smart_format=True,
            punctuate=True,
            numerals=True,
            endpointing_ms=175,
            language="multi",
            filler_words=False,
            profanity_filter=False 
        )
        vad_instance = silero.VAD.load()
        turn_detector = MultilingualModel()
        
        logger.warning("Using untracked AI components due to tracking setup error")
        return {
            "llm": llm,
            "tts": tts,
            "stt": stt,
            "vad": vad_instance,
            "turn_detection": turn_detector
        }
