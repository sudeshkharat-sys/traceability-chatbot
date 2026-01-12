"""
Response Formatter
Formats agent responses and query results for API consumption
"""

import logging
from typing import Any, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Formats agent responses and data for API consumption
    """

    @staticmethod
    def format_chat_response(
        message_id: int,
        response_content: str,
        timestamp: datetime = None,
        similar_docs: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Format a chat response for API
        
        Args:
            message_id: Unique message identifier
            response_content: The response text
            timestamp: Response timestamp
            similar_docs: Optional similar documents/citations
            
        Returns:
            Formatted response dictionary
        """
        try:
            formatted_response = {
                "messageId": message_id,
                "chat_response": {
                    "response": response_content,
                    "similar_docs": similar_docs or []
                },
                "timestamp": (timestamp or datetime.utcnow()).isoformat(),
                "needs_clarification": False
            }
            
            return formatted_response
            
        except Exception as e:
            logger.error(f"Error formatting chat response: {e}")
            raise

    @staticmethod
    def format_query_result(
        query: str,
        records: List[Dict],
        explanation: str = None
    ) -> Dict[str, Any]:
        """
        Format Cypher query results
        
        Args:
            query: The executed Cypher query
            records: Query result records
            explanation: Optional query explanation
            
        Returns:
            Formatted query result
        """
        try:
            return {
                "query": query,
                "records": records,
                "count": len(records),
                "explanation": explanation,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error formatting query result: {e}")
            raise

    @staticmethod
    def format_error_response(error_message: str, error_type: str = "general") -> Dict[str, Any]:
        """
        Format an error response
        
        Args:
            error_message: Error message
            error_type: Type of error
            
        Returns:
            Formatted error response
        """
        return {
            "error": True,
            "error_type": error_type,
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def format_streaming_event(
        event_type: str,
        content: Any,
        step: str = None
    ) -> Dict[str, Any]:
        """
        Format a streaming event
        
        Args:
            event_type: Type of event (token, thinking, tool_call, etc.)
            content: Event content
            step: Optional step description
            
        Returns:
            Formatted streaming event
        """
        event = {
            "type": event_type,
            "content": content
        }
        
        if step:
            event["step"] = step
        
        return event

    @staticmethod
    def format_traceability_summary(
        batch_code: str,
        batch_date: str,
        shift: str,
        warranty_failure: bool = False,
        warranty_note: str = None,
        esqa_failure: bool = False,
        esqa_concern: str = None,
        cpk_value: float = None
    ) -> Dict[str, Any]:
        """
        Format traceability summary table
        
        Args:
            batch_code: Batch code
            batch_date: Manufacturing date
            shift: Manufacturing shift
            warranty_failure: Has warranty failure
            warranty_note: Warranty failure note
            esqa_failure: Has eSQA failure
            esqa_concern: eSQA concern description
            cpk_value: Cpk value
            
        Returns:
            Formatted traceability summary
        """
        return {
            "batch_code": batch_code,
            "manufacturing_date": batch_date,
            "shift": shift,
            "warranty": {
                "has_failure": warranty_failure,
                "note": warranty_note or "None"
            },
            "esqa": {
                "has_failure": esqa_failure,
                "concern": esqa_concern or "None"
            },
            "cpk_value": cpk_value or "N/A"
        }

    @staticmethod
    def format_batch_list(batches: List[Dict]) -> List[Dict]:
        """
        Format a list of batch information
        
        Args:
            batches: List of batch dictionaries
            
        Returns:
            Formatted batch list
        """
        try:
            formatted = []
            for batch in batches:
                formatted.append({
                    "batch_code": batch.get("batch_code"),
                    "date": batch.get("date") or batch.get("batch_date"),
                    "shift": batch.get("shift"),
                    "failures": batch.get("failures", 0)
                })
            return formatted
        except Exception as e:
            logger.error(f"Error formatting batch list: {e}")
            return batches

    @staticmethod
    def truncate_text(text: str, max_length: int = 200) -> str:
        """
        Truncate text to maximum length
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            
        Returns:
            Truncated text
        """
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."

