/**
 * Conversation Service
 * Handles all API calls related to conversations
 */

import { backend_url, backend_url_ws, CURRENT_USER_ID } from "./config";

class ConversationService {
  /**
   * Initiate a new conversation
   * @param {string} agentType - Type of agent ('analyst' or 'cypher')
   * @returns {Promise<{conversationId: number, initial_message: string}>}
   */
  async initiateConversation(agentType = "analyst") {
    try {
      const response = await fetch(`${backend_url}/conversations/initiate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: CURRENT_USER_ID,
          agent_type: agentType,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to initiate conversation");
      }

      return await response.json();
    } catch (error) {
      console.error("Error initiating conversation:", error);
      throw error;
    }
  }

  /**
   * Get conversation history for the current user
   * @param {string} agentType - Filter by agent type
   * @returns {Promise<Array>}
   */
  async getConversationHistory(agentType = "analyst") {
    try {
      const response = await fetch(
        `${backend_url}/conversations/user/${CURRENT_USER_ID}/history?agent_type=${agentType}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to fetch conversation history");
      }

      const data = await response.json();
      return data.response || [];
    } catch (error) {
      console.error("Error fetching conversation history:", error);
      throw error;
    }
  }

  /**
   * Get complete conversation with all messages
   * @param {number} conversationId - Conversation ID
   * @returns {Promise<Object>}
   */
  async getConversation(conversationId) {
    try {
      const response = await fetch(
        `${backend_url}/conversations/${conversationId}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to fetch conversation");
      }

      const data = await response.json();
      return data.response;
    } catch (error) {
      console.error("Error fetching conversation:", error);
      throw error;
    }
  }

  /**
   * Delete a conversation
   * @param {number} conversationId - Conversation ID
   * @returns {Promise<Object>}
   */
  async deleteConversation(conversationId) {
    try {
      const response = await fetch(
        `${backend_url}/conversations/delete/${conversationId}`,
        {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to delete conversation");
      }

      return await response.json();
    } catch (error) {
      console.error("Error deleting conversation:", error);
      throw error;
    }
  }

  /**
   * Submit feedback for a message
   * @param {number} conversationId - Conversation ID
   * @param {number} messageId - Message ID
   * @param {string} feedback - Feedback ('positive' or 'negative')
   * @param {string} comment - Optional comment for negative feedback
   * @returns {Promise<Object>}
   */
  async submitFeedback(conversationId, messageId, feedback, comment = null) {
    try {
      const response = await fetch(
        `${backend_url}/conversations/${conversationId}/messages/${messageId}/feedback`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: CURRENT_USER_ID,
            feedback: feedback,
            negative_feedback_comment: comment,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to submit feedback");
      }

      return await response.json();
    } catch (error) {
      console.error("Error submitting feedback:", error);
      throw error;
    }
  }

  /**
   * Create WebSocket connection for streaming responses
   * @param {number} conversationId - Conversation ID
   * @param {Function} onMessage - Callback for incoming messages
   * @param {Function} onError - Callback for errors
   * @param {Function} onClose - Callback for connection close
   * @returns {WebSocket}
   */
  createWebSocketConnection(
    conversationId,
    onMessage,
    onError = null,
    onClose = null
  ) {
    const wsUrl = `${backend_url_ws}/conversations/${conversationId}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected for conversation:", conversationId);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error("Error parsing WebSocket message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      if (onError) onError(error);
    };

    ws.onclose = () => {
      console.log("WebSocket closed for conversation:", conversationId);
      if (onClose) onClose();
    };

    return ws;
  }

  /**
   * Send a message through WebSocket
   * @param {WebSocket} ws - WebSocket connection
   * @param {string} userMessage - User's message
   * @param {string} agentType - Type of agent
   */
  sendMessage(ws, userMessage, agentType = "analyst") {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          user_id: CURRENT_USER_ID,
          user_message: userMessage,
          agent_type: agentType,
        })
      );
    } else {
      throw new Error("WebSocket is not connected");
    }
  }
}

// Export singleton instance
const conversationService = new ConversationService();
export default conversationService;

