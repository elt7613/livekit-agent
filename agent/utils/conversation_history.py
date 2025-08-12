import asyncio
import json
from livekit.agents import ConversationItemAddedEvent
from livekit.agents.llm import ImageContent, AudioContent
from livekit import rtc
import logging
from storage.save_call_conversation import save_conversation
import datetime,pytz

logger = logging.getLogger("calling-agent")

class ConversationHistory:
    def __init__(self, room: rtc.Room, user_id:str, workflow_id: str, call_id:str):
        self.room = room
        self.user_id = user_id
        self.workflow_id = workflow_id
        self.call_id = call_id
        self.conversation_history = []
        self.ist_tz = pytz.timezone("Asia/Kolkata")

    async def _save_conversation(self):
        """
        Saves conversation history to a JSON file named after the call ID.
        """
        filename = f"conversation_{self.call_id}.json"
        try:
            # Save to Database
            await save_conversation(
                user_id=self.user_id,
                workflow_id=self.workflow_id,
                call_id=self.call_id,
                messages=self.conversation_history
            )

            # Save locally
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({"conversation": self.conversation_history}, f, indent=2, ensure_ascii=False)
            logger.info(f"Conversation history saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")

    def _on_conversation_item_added(self, event: ConversationItemAddedEvent):
        """Process both user and agent messages when they are committed to chat history."""
        item = event.item
        role = item.role  # Will be "user" or "assistant"
        
        # Extract text content
        content = item.text_content
        if not content and item.content:
            # Handle different content types
            content_parts = []
            for content_item in item.content:
                if isinstance(content_item, str):
                    content_parts.append(content_item)
                elif isinstance(content_item, ImageContent):
                    content_parts.append("[image]")
                elif isinstance(content_item, AudioContent):
                    content_parts.append(f"[audio: {content_item.transcript}]")
            content = " ".join(content_parts)
        
        if content:
            logger.info(f"{role.capitalize()} message: {content}")
            self.conversation_history.append({
                "role": role,
                "content": content,
                "interrupted": getattr(item, 'interrupted', False),
                "timestamp": datetime.datetime.now(self.ist_tz).strftime("%Y-%m-%d %I:%M:%S %p %Z")
            })

    async def setup_conversation_monitoring(self, session):
        """Set up event listeners for conversation monitoring."""
        # Listen to conversation_item_added event for both user and agent messages
        session.on("conversation_item_added", self._on_conversation_item_added)
        logger.info("Conversation monitoring setup complete")
