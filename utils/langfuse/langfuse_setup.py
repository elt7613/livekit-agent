from livekit.agents.telemetry import set_tracer_provider
import os,logging, atexit
from dotenv import load_dotenv
import base64
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor
from opentelemetry import trace

load_dotenv()

logger = logging.getLogger("calling-agent")

_TRACE_PROVIDER = None


# Langfuse Setup
async def setup_langfuse(
    *,
    host: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
):
    """
    Setup Langfuse tracing with LiveKit Agents
    Based on official Langfuse documentation
    """
    try:
        public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        host = host or os.getenv("LANGFUSE_HOST")

        if not public_key or not secret_key or not host:
            raise ValueError("LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST must be set")

        langfuse_auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host.rstrip('/')}/api/public/otel"
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {langfuse_auth}"

        trace_provider = TracerProvider()
        # Use BatchSpanProcessor to avoid blocking the critical call path
        trace_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(),
                max_queue_size=2048,
                schedule_delay_millis=1000,
                max_export_batch_size=512,
            )
        )
        
        # Set the global tracer provider
        trace.set_tracer_provider(trace_provider)
        set_tracer_provider(trace_provider)
        
        # Store globally and register shutdown on process exit to flush spans
        global _TRACE_PROVIDER
        _TRACE_PROVIDER = trace_provider
        
        def _shutdown_tracing():
            try:
                if _TRACE_PROVIDER is not None:
                    # Try to flush quickly to avoid losing spans on abrupt exit
                    if hasattr(_TRACE_PROVIDER, "force_flush"):
                        _TRACE_PROVIDER.force_flush(timeout_millis=1500)
                    if hasattr(_TRACE_PROVIDER, "shutdown"):
                        _TRACE_PROVIDER.shutdown()
            except Exception as e:
                logger.warning(f"Error during tracer provider shutdown: {e}")
        
        # Ensure export on interpreter shutdown
        atexit.register(_shutdown_tracing)
        
        logger.info("Langfuse setup completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to setup Langfuse: {e}. Continuing without Langfuse tracing.")
        return False