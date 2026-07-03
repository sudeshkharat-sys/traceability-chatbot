import React, { useState, useMemo } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./ChatMessage.css";
import mahindraLogo from "../assests/logo.png";
import { conversationService } from "../services/api";
import FeedbackModal from "./FeedbackModal";
import ChartComponent from "./ChartComponent";
import CitationsTable from "./CitationsTable";
import QueryResultsTable from "./QueryResultsTable";
import ThinkingStepsDisplay from "./ThinkingStepsDisplay";
import { fixMarkdownTables } from "../utils/markdownUtils";
import { extractQueryResultsTable } from "../utils/queryTableUtils";

const ChatMessage = ({ message, conversationId, onOpenPdf }) => {
  const isUser = message.sender === "user";
  const [feedback, setFeedback] = useState(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [feedbackType, setFeedbackType] = useState(null);

  // If the response contains a fenced ```json result block (QLense Phase 1
  // issue table), pull it out as structured rows for a real <table> and
  // strip it from the text so it isn't also shown as a raw code block.
  const { rows: queryResultRows, strippedText } = useMemo(
    () => extractQueryResultsTable(message.text),
    [message.text]
  );

  // Fix markdown tables before rendering
  // Only apply strict fixes when message is complete (has messageId)
  // During streaming, use lenient mode to avoid breaking incomplete tables
  const fixedMarkdown = useMemo(() => {
    if (!strippedText) return "";
    const isComplete = !!message.messageId;
    return fixMarkdownTables(strippedText, isComplete);
  }, [strippedText, message.messageId]);

  const handleFeedback = async (type) => {
    if (!conversationId || !message.messageId) return;

    try {
      if (type === "positive") {
        await conversationService.submitFeedback(
          conversationId,
          message.messageId,
          type
        );
        setFeedback(type);
      } else {
        setFeedbackType(type);
        setShowFeedbackModal(true);
      }
    } catch (error) {
      console.error("Error submitting feedback:", error);
      alert("Failed to submit feedback");
    }
  };

  const handleFeedbackModalSubmit = async (feedbackData) => {
    if (!conversationId || !message.messageId) return;

    setIsSubmittingFeedback(true);
    try {
      await conversationService.submitFeedback(
        conversationId,
        message.messageId,
        feedbackType,
        feedbackData.comment,
        feedbackData.rating,
        feedbackData.reason
      );
      setFeedback(feedbackType);
      setShowFeedbackModal(false);
      setFeedbackType(null);
    } catch (error) {
      console.error("Error submitting feedback:", error);
      alert("Failed to submit feedback");
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const handleFeedbackModalClose = () => {
    setShowFeedbackModal(false);
    setFeedbackType(null);
  };

  return (
    <div
      className={`message ${isUser ? "user-message" : "bot-message"} ${
        message.isError ? "error-message" : ""
      } message-mounted`}
      data-message-id={message.messageId}
    >
      <div className={`message-avatar ${isUser ? "user-avatar" : ""}`}>
        {isUser ? (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
          </svg>
        ) : (
          <img src={mahindraLogo} alt="Bot" />
        )}
      </div>
      <div className="message-content">
        <div className="message-bubble">
          {!isUser ? (
            <>
              {message.text ? (
                <>
                  {/* Render chart ABOVE text if chart_data is present */}
                  {message.chart_data && (
                    <ChartComponent chartData={message.chart_data} />
                  )}
                  <div className="bot-message-markdown">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        table: ({ node, ...props }) => (
                          <div className="table-scroll-wrapper">
                            <table {...props} />
                          </div>
                        ),
                      }}
                    >
                      {fixedMarkdown}
                    </ReactMarkdown>
                  </div>

                  {/* Render QLense's structured issue-list table, if present */}
                  <QueryResultsTable rows={queryResultRows} />

                  {/* Render citations table if available */}
                  <CitationsTable
                    citations={message.citations || message.similar_docs}
                    onOpenPdf={onOpenPdf}
                  />

                  {/* Reasoning/SQL steps for this turn — collapsed by default,
                      so users can inspect what query the agent actually ran */}
                  {message.thinkingSteps && message.thinkingSteps.length > 0 && (
                    <details className="message-reasoning-details">
                      <summary>Show reasoning</summary>
                      <ThinkingStepsDisplay
                        steps={message.thinkingSteps}
                        isStreaming={false}
                        currentStep=""
                      />
                    </details>
                  )}
                </>
              ) : (
                <div className="typing-indicator">
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              )}
            </>
          ) : (
            <p className="message-text">{message.text}</p>
          )}
        </div>

        {!isUser && !message.isError && message.messageId && message.text && (
          <div className="message-feedback">
            <button
              className={`feedback-btn ${
                feedback === "positive" ? "active" : ""
              }`}
              onClick={() => handleFeedback("positive")}
              disabled={feedback !== null}
              title="Good response"
            >
              <ThumbsUp size={18} />
            </button>
            <button
              className={`feedback-btn ${
                feedback === "negative" ? "active" : ""
              }`}
              onClick={() => handleFeedback("negative")}
              disabled={feedback !== null}
              title="Bad response"
            >
              <ThumbsDown size={18} />
            </button>
          </div>
        )}

        <FeedbackModal
          isOpen={showFeedbackModal}
          onClose={handleFeedbackModalClose}
          onSubmit={handleFeedbackModalSubmit}
          isSubmitting={isSubmittingFeedback}
        />
      </div>
    </div>
  );
};

// Don't memoize - let React handle updates naturally (like Agentic-AI-Framework)
// The flickering is caused by preventing updates, not by allowing them
export default ChatMessage;
