import React, { useState, useRef, useMemo } from "react";
import "./ChatArea.css";
import ChatMessage from "./ChatMessage";
import ThinkingStepsDisplay from "./ThinkingStepsDisplay";
import LoadingAnimation from "./LoadingAnimation";
import mahindraLogo from "../assests/logo.png";

const ChatArea = ({
  messages,
  onSendMessage,
  userName,
  isLoading,
  currentConversationId,
  thinkingSteps = [],
  currentThinkingStep = "",
  onOpenPdf,
}) => {
  const [inputMessage, setInputMessage] = useState("");
  const [isScrolled, setIsScrolled] = useState(false);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatContentRef = useRef(null);
  const isAutoScrollingRef = useRef(false);
  const userHasScrolledRef = useRef(false);
  const scrollTimeoutRef = useRef(null);

  const handleSend = () => {
    if (inputMessage.trim() && !isLoading) {
      onSendMessage(inputMessage);
      setInputMessage("");
      // Force scroll to bottom when user sends a new message
      setUserScrolledUp(false);
      userHasScrolledRef.current = false;
      // Scroll to bottom after a brief delay to ensure message is rendered
      setTimeout(() => {
        scrollToBottom();
      }, 50);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Check if user is at the bottom of chat
  const isAtBottom = () => {
    const chatContent = chatContentRef.current;
    if (!chatContent) return true;

    const threshold = 50; // pixels from bottom
    const position = chatContent.scrollTop + chatContent.clientHeight;
    const height = chatContent.scrollHeight;
    const result = height - position < threshold;


    return result;
  };

  const scrollToBottom = () => {
    isAutoScrollingRef.current = true;
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    setUserScrolledUp(false);
    userHasScrolledRef.current = false;
    // Reset auto-scrolling flag after animation completes
    setTimeout(() => {
      isAutoScrollingRef.current = false;
    }, 500);
  };

  // Simplified auto-scroll like Agentic-AI-Framework - only scroll when user is near bottom
  React.useEffect(() => {
    const chatContent = chatContentRef.current;
    if (!chatContent) return;

    // Calculate if user is near bottom (within 100px)
    const isNearBottom = () => {
      const { scrollTop, scrollHeight, clientHeight } = chatContent;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      return distanceFromBottom < 100;
    };

    // Only auto-scroll if:
    // 1. User is near the bottom
    // 2. User hasn't manually scrolled up
    if (!userHasScrolledRef.current && isNearBottom()) {
      // Simple scroll to bottom - let browser handle batching
      chatContent.scrollTop = chatContent.scrollHeight;
    }
  }, [messages, isLoading]);

  // Cleanup timeouts on unmount
  React.useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
        scrollTimeoutRef.current = null;
      }
    };
  }, []);

  // Detect scroll to show/hide top fade and track user scroll behavior
  React.useEffect(() => {
    const chatContent = chatContentRef.current;
    if (!chatContent) return;

    let scrollTimeout;

    const handleScroll = () => {
      const scrollTop = chatContent.scrollTop;
      // Ignore scroll events triggered by auto-scroll
      if (isAutoScrollingRef.current) {
        return;
      }

      setIsScrolled(scrollTop > 20);

      // Clear existing timeout
      if (scrollTimeout) {
        clearTimeout(scrollTimeout);
      }

      // Debounce scroll detection
      scrollTimeout = setTimeout(() => {
        const atBottom = isAtBottom();


        // If user scrolled and not at bottom, mark as user scroll
        if (!atBottom) {
          userHasScrolledRef.current = true;
          setUserScrolledUp(true);
        } else {
          userHasScrolledRef.current = false;
          setUserScrolledUp(false);
        }
      }, 100);
    };

    chatContent.addEventListener("scroll", handleScroll);
    return () => {
      chatContent.removeEventListener("scroll", handleScroll);
      if (scrollTimeout) {
        clearTimeout(scrollTimeout);
      }
    };
  }, []);

  const handleFileUpload = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      console.log("File selected:", file.name);
      // Handle file upload logic here
    }
  };

  const getCurrentGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good Morning";
    if (hour < 17) return "Good Afternoon";
    return "Good Evening";
  };

  // Check if thinkingSteps or currentThinkingStep has any valid content (todos or reasoning)
  // Memoized to prevent recalculation on every render
  const hasValidThinkingContent = useMemo(() => {
    // Check currentThinkingStep first (streaming content)
    if (currentThinkingStep && currentThinkingStep.trim().length > 0) {
      const content = currentThinkingStep;
      // Check for todos
      if (
        content.includes("**Task Plan**") ||
        content.includes("- ⏳") ||
        content.includes("- ✅")
      ) {
        return true;
      }
      // Check for reasoning
      if (content.includes("🤔 Reasoning") || content.includes("Reasoning:")) {
        const reasoningText = content
          .replace(/🤔\s*Reasoning:?\s*/i, "")
          .trim();
        if (reasoningText && reasoningText.length > 0) {
          return true;
        }
      }
    }

    if (thinkingSteps.length === 0) return false;

    // Check if any step has valid content
    return thinkingSteps.some((step) => {
      const content = step.content || "";
      const stepName = step.step || "";

      // Check for todos
      if (
        stepName?.toLowerCase() === "planning" ||
        content.includes("**Task Plan**") ||
        content.includes("- ⏳") ||
        content.includes("- ✅")
      ) {
        return true;
      }

      // Check for reasoning
      if (
        stepName?.toLowerCase() === "reasoning" ||
        content.includes("🤔 Reasoning") ||
        content.includes("Reasoning:")
      ) {
        const reasoningText = content
          .replace(/🤔\s*Reasoning:?\s*/i, "")
          .trim();
        return reasoningText && reasoningText.length > 0;
      }

      return false;
    });
  }, [currentThinkingStep, thinkingSteps]);

  return (
    <div className="chat-area">
      <div className="chat-header">
        <img src={mahindraLogo} alt="Mahindra" className="mahindra-logo" />
      </div>

      <div
        ref={chatContentRef}
        className={`chat-content ${messages.length === 0 ? "centered" : ""} ${
          isScrolled ? "scrolled" : ""
        }`}
      >
        {messages.length === 0 ? (
          <div className="welcome-container">
            <div className="greeting-with-avatar">
              <div className="welcome-avatar">
                <img src={mahindraLogo} alt="Bot" className="bot-avatar" />
              </div>
              <h2 className="welcome-greeting">
                {getCurrentGreeting()},{userName}
              </h2>
            </div>

            {/* Welcome Message Box */}
            <div className="welcome-message-wrapper">
              <input
                type="text"
                className="welcome-input-field"
                placeholder="How can i help you today ?"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
              />

              <div className="welcome-input-row">
                <button
                  className="action-circle-btn upload"
                  onClick={handleFileUpload}
                >
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z" />
                  </svg>
                </button>

                <button
                  className="action-circle-btn send"
                  onClick={handleSend}
                  disabled={!inputMessage.trim()}
                >
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-container">
            {messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                message={message}
                conversationId={currentConversationId}
                onOpenPdf={onOpenPdf}
              />
            ))}

            {/* Show loading/thinking AFTER last user message, BEFORE bot response */}
            {/* Moved outside map to prevent conditional mount/unmount flickering */}
            {messages.length > 0 &&
              messages[messages.length - 1].sender === "user" &&
              (isLoading || thinkingSteps.length > 0) && (
                <React.Fragment>
                  {/* Show loader when isLoading is true and no valid content yet */}
                  {isLoading && !hasValidThinkingContent && (
                    <LoadingAnimation message="Thinking..." />
                  )}
                  {/* Show thinking steps if we have any content */}
                  {thinkingSteps.length > 0 && (
                    <ThinkingStepsDisplay
                      steps={thinkingSteps}
                      isStreaming={isLoading && !!currentThinkingStep}
                      currentStep={currentThinkingStep}
                    />
                  )}
                </React.Fragment>
              )}
            <div ref={messagesEndRef} />

            {/* Scroll to bottom button - shows when user scrolls up during streaming */}
            {userScrolledUp && isLoading && (
              <button className="scroll-to-bottom-btn" onClick={scrollToBottom}>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M7 13l5 5 5-5M7 6l5 5 5-5" />
                </svg>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Bottom Input - Only visible when there are messages */}
      {messages.length > 0 && (
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <button className="input-action-btn" onClick={handleFileUpload}>
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z" />
              </svg>
            </button>
            <input
              type="text"
              className="chat-input"
              placeholder="Type your message here..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
            />
            <button
              className="input-action-btn send"
              onClick={handleSend}
              disabled={!inputMessage.trim() || isLoading}
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <input
        type="file"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
        accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
      />
    </div>
  );
};

export default ChatArea;
