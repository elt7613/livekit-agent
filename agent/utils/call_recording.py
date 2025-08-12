import logging
from dotenv import load_dotenv
from livekit import api
from livekit.agents import get_job_context
from datetime import datetime
import os

load_dotenv()

# Set up logging with console handler
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calling-agent")

class CallRecording:
    def __init__(self) -> None:
        self.recording_id = None
        self.is_recording = False
        
    async def _get_livekit_api(self):
        """Get LiveKit API instance with credentials"""
        ctx = get_job_context()
        if ctx is None:
            raise Exception("No job context available")
        return ctx.api
        
    async def _start_recording_internal(self):
        """Internal method to start recording"""
        try:
            ctx = get_job_context()
            if ctx is None:
                raise Exception("No job context available")
            
            livekit_api = await self._get_livekit_api()
            
            # Create a unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"call_recording_{ctx.room.name}_{timestamp}.ogg"
            
            # Check for MinIO/S3 credentials in environment
            s3_endpoint = os.getenv("AWS_S3_ENDPOINT")
            s3_access_key = os.getenv("AWS_S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
            s3_secret_key = os.getenv("AWS_S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
            s3_bucket = os.getenv("AWS_S3_BUCKET")
            s3_region = os.getenv("AWS_S3_REGION", "us-east-1")
            s3_force_path_style = os.getenv("AWS_S3_FORCE_PATH_STYLE", "false").lower() == "true"
            
            if not s3_access_key or not s3_secret_key or not s3_bucket:
                raise Exception("S3/MinIO credentials not found. Please set AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, and AWS_S3_BUCKET environment variables.")
            
            # Create file output with proper structure
            file_output = api.EncodedFileOutput(
                file_type=api.EncodedFileType.OGG,
                filepath=filename, 
                s3=api.S3Upload(
                    access_key=s3_access_key,
                    secret=s3_secret_key,
                    bucket=s3_bucket,
                    region=s3_region,
                    force_path_style=s3_force_path_style,
                    endpoint=s3_endpoint if s3_endpoint else "",
                ),
            )
            
            # Create the egress request with proper structure
            request = api.RoomCompositeEgressRequest(
                room_name=ctx.room.name,
                layout="speaker",
                audio_only=True,
                file_outputs=[file_output],
            )
            
            if s3_endpoint:
                logger.info(f"Using MinIO storage for recording: {s3_endpoint}")
            else:
                logger.info("Using S3 storage for recording")
            
            logger.info(f"Recording will be saved to {s3_bucket}/{filename}")
            
            response = await livekit_api.egress.start_room_composite_egress(request)
            self.recording_id = response.egress_id
            self.is_recording = True
            
            logger.info(f"Started recording with ID: {self.recording_id}")
            logger.info(f"Recording will be saved as: {filename}")
            logger.info(f"Recording status: {response.status}")
            if hasattr(response, 'file_results') and response.file_results:
                for file_result in response.file_results:
                    logger.info(f"Recording file location: {file_result.filename}")
            
            return self.recording_id
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            raise
    
    async def _stop_recording_internal(self):
        """Internal method to stop recording"""
        try:
            if not self.is_recording or not self.recording_id:
                return None
            
            livekit_api = await self._get_livekit_api()
            
            # Stop the recording
            request = api.StopEgressRequest(egress_id=self.recording_id)
            response = await livekit_api.egress.stop_egress(request)
            
            self.is_recording = False
            recording_id = self.recording_id
            self.recording_id = None
            
            logger.info(f"Stopped recording with ID: {recording_id}")
            logger.info(f"Final recording status: {response.status}")
            
            # Log file locations when recording is complete
            if hasattr(response, 'file_results') and response.file_results:
                for file_result in response.file_results:
                    logger.info(f"Recording saved to: {file_result.filename}")
                    logger.info(f"File size: {file_result.size} bytes")
                    logger.info(f"Download URL: {file_result.download_url if hasattr(file_result, 'download_url') else 'Not available'}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            raise