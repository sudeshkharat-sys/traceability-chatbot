import React, { useState } from "react";
import { X, Send } from "lucide-react";
import "./FeedbackModal.css";

const FeedbackModal = ({ isOpen, onClose, onSubmit, isSubmitting }) => {
  const [rating, setRating] = useState(1);
  const [comment, setComment] = useState("");
  const [selectedReason, setSelectedReason] = useState("");

  const feedbackReasons = [
    "Inaccurate information",
    "Unhelpful response",
    "Poor formatting",
    "Irrelevant to my question",
    "Technical issues",
    "Too slow response",
    "Missing information",
    "Confusing explanation",
    "Other",
  ];

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!comment.trim() && !selectedReason) {
      alert("Please provide either a reason or comment for your feedback.");
      return;
    }

    const feedbackData = {
      rating: rating,
      comment: comment.trim() || selectedReason,
      reason: selectedReason,
      additionalComment:
        selectedReason && comment.trim() ? comment.trim() : null,
    };

    onSubmit(feedbackData);
  };

  const handleClose = () => {
    // Reset form when closing
    setRating(1);
    setComment("");
    setSelectedReason("");
    onClose();
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="feedback-modal-overlay" onClick={handleOverlayClick}>
      <div
        className="feedback-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="feedback-modal-header">
          <h3>Help us improve</h3>
          <button
            className="feedback-modal-close"
            onClick={handleClose}
            disabled={isSubmitting}
            type="button"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="feedback-form">
          <div className="feedback-section">
            <label className="feedback-label">
              How would you rate this response?
            </label>
            <div className="rating-container">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`rating-star ${rating >= value ? "active" : ""}`}
                  onClick={() => setRating(value)}
                  disabled={isSubmitting}
                >
                  ★
                </button>
              ))}
              <span className="rating-text">
                {rating === 1 && "Very Poor"}
                {rating === 2 && "Poor"}
                {rating === 3 && "Average"}
                {rating === 4 && "Good"}
                {rating === 5 && "Excellent"}
              </span>
            </div>
          </div>

          <div className="feedback-section">
            <label className="feedback-label">
              What was the main issue? (Optional)
            </label>
            <div className="reason-buttons">
              {feedbackReasons.map((reason) => (
                <button
                  key={reason}
                  type="button"
                  className={`reason-button ${
                    selectedReason === reason ? "selected" : ""
                  }`}
                  onClick={() =>
                    setSelectedReason(selectedReason === reason ? "" : reason)
                  }
                  disabled={isSubmitting}
                >
                  {reason}
                </button>
              ))}
            </div>
          </div>

          <div className="feedback-section">
            <label className="feedback-label" htmlFor="feedback-comment">
              Additional comments (Optional)
            </label>
            <textarea
              id="feedback-comment"
              className="feedback-textarea"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Please provide specific details about what could be improved..."
              rows={4}
              disabled={isSubmitting}
              maxLength={1000}
            />
            <div className="character-count">
              {comment.length}/1000 characters
            </div>
          </div>

          <div className="feedback-actions">
            <button
              type="button"
              className="feedback-cancel-btn"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="feedback-submit-btn"
              disabled={isSubmitting || (!comment.trim() && !selectedReason)}
            >
              {isSubmitting ? (
                <span className="loading-spinner">Submitting...</span>
              ) : (
                <>
                  <Send size={16} />
                  Submit Feedback
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FeedbackModal;

