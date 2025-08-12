import os
import json
import time
import logging
from datetime import datetime
import pytz,uuid
from livekit.agents import get_job_context
from storage.save_call_metadata import save_metadata
from livekit import rtc
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calling-agent")


class CallMetadata:
    # Constants
    IST_TIMEZONE = "Asia/Kolkata"
    SHORT_CALL_THRESHOLD = 3  # seconds
    
    # Status mapping for responses
    STATUS_MAPPING = {
        1: 'completed',      # EGRESS_STATUS_ACTIVE
        2: 'completed',      # EGRESS_STATUS_ENDED
        3: 'failed',         # EGRESS_STATUS_FAILED
        4: 'aborted',        # EGRESS_STATUS_ABORTED
        5: 'limit_reached'   # EGRESS_STATUS_LIMIT_REACHED
    }

    def __init__(self, config):
        ctx = get_job_context()
        self.ctx = ctx

        self.config = config

        self.phone_numbers = {
            'agent_number': '',
            'customer_number': '',
            'from_number': '',
            'to_number': ''
        }
        # Idempotency flag to avoid duplicate metadata saves
        self._metadata_saved = False
        

    async def format_time_ist(self, unix_timestamp: str) -> str:
        """
        Convert Unix timestamp to IST format with AM/PM
        
        Args:
            unix_timestamp: takes the unix time stamp
            
        Returns:
            str: Date and Time
        """
        try:
            # Convert to datetime object
            dt = datetime.fromtimestamp(unix_timestamp)
            # Convert to IST timezone
            ist = pytz.timezone(self.IST_TIMEZONE)
            dt_ist = dt.astimezone(ist)
            
            return dt_ist.strftime("%d-%m-%Y %I:%M:%S %p IST")
        except:
            return "Invalid timestamp"

    def _extract_basic_metadata(self) -> dict:
        """Extract basic metadata from config"""
        system_agent_name = self.config.get("system_agent_name")
        room_name = self.ctx.room.name 
        agent_name = self.config.get("agent_name")
        
        return {
                'system_agent_name': system_agent_name,
                'room_name': room_name,
                'agent_name': agent_name
            }

    def _determine_call_direction(self) -> tuple:
        """Determine call direction and return direction info"""
        outbound_trunk_id = self.config.get('outbound_trunk_id')
        inbound_trunk_id = self.config.get('inbound_trunk_id')
        number_to_call = self.config.get('number_to_call')

        if number_to_call or outbound_trunk_id:
            direction = 'outbound'
            trunk_info = {
                'outbound_trunk_id': outbound_trunk_id,
                'inbound_trunk_id': ''
            }
        else:
            direction = 'inbound'
            trunk_info = {
                'outbound_trunk_id': '',
                'inbound_trunk_id': inbound_trunk_id
            }
            
        logger.info(f"Call direction determined as: {direction}")
        return direction, trunk_info

    def _get_phone_numbers(self, direction: str) -> dict:
        """Get phone numbers based on call direction"""
        if direction == 'outbound':
            numbers =  {
                'agent_number': self.config.get('agent_number', ''),
                'customer_number': self.config.get('number_to_call', ''),
                'from_number': self.config.get('number_from', ''),
                'to_number': self.config.get('number_to_call', '')
            }
        else:
            numbers =  {
                'agent_number': self.config.get('agent_number', ''),
                'customer_number': '',
                'from_number': '',
                'to_number': self.config.get('agent_number', '')
            }

        # Preserve any previously cached values (e.g., set early via update_inbound_phone_numbers)
        final_numbers = {}
        for k, v in numbers.items():
            prev = self.phone_numbers.get(k)
            final_numbers[k] = prev if prev else v

        # Store the numbers for later updates
        self.phone_numbers.update(final_numbers)
        return self.phone_numbers

    def update_inbound_phone_numbers(self, caller_number: str) -> None:
        """Update customer phone number for inbound calls"""
        self.phone_numbers["customer_number"] = caller_number
        self.phone_numbers["from_number"] = caller_number

    def _build_base_metadata(self) -> dict:
        """Build base metadata common to both answered and unanswered calls"""
        metadata = self._extract_basic_metadata()
        
        # Determine call direction
        direction, trunk_info = self._determine_call_direction()
        metadata['call_direction'] = direction
        metadata.update(trunk_info)
        
        # Get phone numbers
        phone_numbers = self._get_phone_numbers(direction)
        metadata.update(phone_numbers)
        
        return metadata

    async def _set_timing_metadata(self, metadata: dict, start_time: float = None, end_time: float = None) -> None:
        """Set timing-related metadata"""
        if start_time is None:
            start_time = time.time()
        if end_time is None:
            end_time = time.time()
            
        metadata['start_time'] = await self.format_time_ist(start_time)
        metadata['end_time'] = await self.format_time_ist(end_time)
        metadata['duration'] = end_time - start_time

    def _determine_call_status(self, response, duration: float) -> tuple:
        """Determine call status and termination reason"""
        if not response:
            has_conversation = hasattr(self, 'conversation_history') and len(self.conversation_history) > 0
            if has_conversation:
                return 'completed_no_recording', 'recording not available'
            else:
                return 'no_recording', 'recording not started'
        
        # Status from response
        if hasattr(response, 'status'):
            status = self.STATUS_MAPPING.get(response.status, 'completed')
        else:
            status = 'completed'
        
        # Check for very short calls
        if duration < self.SHORT_CALL_THRESHOLD:
            has_conversation = hasattr(self, 'conversation_history') and len(self.conversation_history) > 0
            if not has_conversation:
                status = 'possibly_unanswered'
                termination_reason = 'very_short_call'
            else:
                termination_reason = response.error if hasattr(response, 'error') and response.error else 'normal'
        else:
            termination_reason = response.error if hasattr(response, 'error') and response.error else 'normal'
        
        return status, termination_reason

    def _get_recording_filename(self, response) -> str:
        """Extract recording filename from response"""
        if hasattr(response, 'file_results') and response.file_results:
            file_result = response.file_results[0]
            return getattr(file_result, 'filename', 'unknown')
        return ''

    async def _save_metadata_to_storage(self, metadata: dict) -> None:
        """Save metadata to both MongoDB and local file"""
        user_id = self.config.get("user_id")
        workflow_id = self.config.get("workflow_id")
        call_id = self.config.get("call_id") 
        
        # Save to Database
        await save_metadata(
            user_id=user_id,
            workflow_id=workflow_id,
            call_id=call_id,
            metadata=metadata
        )
        
        # Save locally
        filename = f"call_metadata_{call_id}.json"
        metadata_copy = metadata.copy()
        if "_id" in metadata_copy:
            del metadata_copy["_id"]  # Remove ObjectId before saving to JSON
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(metadata_copy, f, indent=2)
        logger.info(f"Call metadata saved to {filename}")

    async def save_unanswered_call_metadata(self, reason: str = "not_answered") -> None:
        """
        Save metadata for calls that are not picked up or fail to connect
        
        Args:
            reason: Reason for call not connecting (default='not_answered')
        
        Returns:
            None
        """
        try:
            # Prevent duplicate saves
            if getattr(self, "_metadata_saved", False):
                logger.warning("Metadata already saved, skipping unanswered-call duplicate save")
                return
            logger.info(f"Saving unanswered call metadata. Reason: {reason}")
            
            # Build base metadata
            metadata = self._build_base_metadata()
            
            # Set timing for unanswered call
            current_time = time.time()
            await self._set_timing_metadata(metadata, current_time, current_time)
            metadata['duration'] = 0
            
            # Set status and termination reason
            metadata['status'] = reason
            metadata['termination_reason'] = reason
            metadata['recording_filename'] = ''
            
            logger.info(f"Unanswered call metadata - Status: {metadata['status']}, Reason: {reason}")
            
            # Save to Database
            await self._save_metadata_to_storage(metadata)
            self._metadata_saved = True
        
        except Exception as e:
            logger.error(f"Error saving unanswered call metadata (non-critical): {e}")

    async def save_call_metadata(self, response) -> None:
        """
        Save metadata for calls that are connected and picked up
        
        Args:
            response: The data to determine wheather the call is picked up or not.The call status.
        
        Returns:
            None
        """
        try:
            # Prevent duplicate saves
            if getattr(self, "_metadata_saved", False):
                logger.warning("Metadata already saved, skipping duplicate save")
                return
            logger.info(f"Saving call metadata. Response: {response}")
            
            # Build base metadata
            metadata = self._build_base_metadata()
            
            logger.info(f"Numbers saved - Agent: {metadata['agent_number']}, Customer: {metadata['customer_number']}")
            
            if response:
                # Extract timestamps from response
                start_timestamp = response.started_at / 1e9 if hasattr(response, 'started_at') and response.started_at else time.time()
                end_timestamp = response.ended_at / 1e9 if hasattr(response, 'ended_at') and response.ended_at else time.time()
                
                # Set timing metadata
                await self._set_timing_metadata(metadata, start_timestamp, end_timestamp)
                
                # Determine status and termination reason
                status, termination_reason = self._determine_call_status(response, metadata['duration'])
                metadata['status'] = status
                metadata['termination_reason'] = termination_reason
                
                # Get recording filename
                metadata['recording_filename'] = self._get_recording_filename(response)
                
            else:
                # No recording response
                current_time = time.time()
                await self._set_timing_metadata(metadata, current_time, current_time)
                metadata['duration'] = 0
                
                # Determine status for no-response scenario
                status, termination_reason = self._determine_call_status(response, 0)
                metadata['status'] = status
                metadata['termination_reason'] = termination_reason
                metadata['recording_filename'] = ''
            
            # Save to Database
            await self._save_metadata_to_storage(metadata)
            self._metadata_saved = True
        
        except Exception as e:
            logger.error(f"Error saving call metadata (non-critical): {e}")
