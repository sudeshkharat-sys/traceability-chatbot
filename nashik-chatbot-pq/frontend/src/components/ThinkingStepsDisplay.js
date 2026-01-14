import React, { useState } from "react";
import "./ThinkingStepsDisplay.css";

const ThinkingStepsDisplay = React.memo(
  ({ steps, isStreaming, currentStep }) => {
    // By default, all todos are collapsed (empty set)
    const [expandedTodos, setExpandedTodos] = useState(new Set());

    // Parse content to detect todo lists and reasoning
    // Also check step.step field to determine type
    const parseContent = (content, stepName) => {
      if (!content) return { type: "text", content: "" };

      // FIRST: Check step name - if step.step is "Reasoning", treat as reasoning
      if (stepName && stepName.toLowerCase() === "reasoning") {
        // Remove any prefix like "🤔 Reasoning:" if present
        const reasoningText = content
          .replace(/🤔\s*Reasoning:?\s*/i, "")
          .trim();
        // Only return reasoning if we have actual content
        if (reasoningText && reasoningText.length > 0) {
          return { type: "reasoning", content: reasoningText };
        }
        // If empty, return as text to avoid empty reasoning boxes
        return { type: "text", content: content };
      }

      // Check if it's a todo list (contains "Task Plan" or markdown list format)
      // OR if step name is "Planning"
      if (
        stepName?.toLowerCase() === "planning" ||
        content.includes("**Task Plan**") ||
        content.includes("- ⏳") ||
        content.includes("- ✅")
      ) {
        const lines = content.split("\n").filter((line) => line.trim());
        const todos = [];
        let inTodoSection = false;

        lines.forEach((line) => {
          if (line.includes("**Task Plan**") || line.includes("Task Plan")) {
            inTodoSection = true;
            return;
          }
          if (
            inTodoSection &&
            (line.includes("- ⏳") || line.includes("- ✅"))
          ) {
            const isCompleted = line.includes("✅");
            const todoText = line.replace(/^[-•]\s*(✅|⏳)\s*/, "").trim();
            todos.push({ text: todoText, completed: isCompleted });
          }
        });

        if (todos.length > 0) {
          return { type: "todo", todos };
        }
      }

      // Check if it's reasoning (contains "Reasoning" or starts with thought)
      if (content.includes("🤔 Reasoning") || content.includes("Reasoning:")) {
        const reasoningText = content
          .replace(/🤔\s*Reasoning:?\s*/i, "")
          .trim();
        // Only return reasoning if we have actual content
        if (reasoningText && reasoningText.length > 0) {
          return { type: "reasoning", content: reasoningText };
        }
        // If empty, return as text to avoid empty reasoning boxes
        return { type: "text", content: content };
      }

      // Default to text
      return { type: "text", content };
    };

    // Separate reasoning and todos, keep all reasoning visible
    // Use timestamp or index to maintain order and avoid duplicates
    const reasoningSteps = [];
    const todoSteps = [];
    const seenContent = new Set(); // Track seen content to avoid duplicates

    steps.forEach((step, index) => {
      const parsed = parseContent(step.content, step.step);

      // Use a more specific key that includes the actual content to prevent duplicates
      const contentKey = `${parsed.type}-${
        parsed.type === "reasoning"
          ? parsed.content
          : parsed.type === "todo"
          ? JSON.stringify(parsed.todos)
          : step.content
      }`;

      // Skip duplicates - check both contentKey and actual content
      if (seenContent.has(contentKey)) {
        return;
      }

      // Also check if reasoning content already exists (exact match or substring)
      if (parsed.type === "reasoning") {
        const alreadyExists = reasoningSteps.some((s) => {
          const existingContent = s.parsed.content || "";
          const newContent = parsed.content || "";
          // Check for exact match
          if (existingContent === newContent) return true;
          // Check if one is a substring of the other (likely duplicate)
          if (existingContent && newContent) {
            if (
              existingContent.includes(newContent) ||
              newContent.includes(existingContent)
            ) {
              // If one is significantly longer, it's likely an update, not a duplicate
              // Only consider it duplicate if they're similar in length (within 20%)
              const lengthDiff = Math.abs(
                existingContent.length - newContent.length
              );
              const avgLength =
                (existingContent.length + newContent.length) / 2;
              if (lengthDiff < avgLength * 0.2) {
                return true;
              }
            }
          }
          return false;
        });
        if (alreadyExists) {
          return;
        }
      }

      // Also check if todo list already exists - if it does, UPDATE it instead of adding new
      if (parsed.type === "todo") {
        const todosKey = JSON.stringify(
          parsed.todos.map((t) => ({ text: t.text, completed: t.completed }))
        );
        // Check if we have a similar todo list (same task texts, even if completion status differs)
        const existingTodoIndex = todoSteps.findIndex((s) => {
          const existingTodos = s.parsed.todos || [];
          const newTodos = parsed.todos || [];
          // Check if they have the same tasks (by text), regardless of completion status
          if (existingTodos.length !== newTodos.length) return false;
          return existingTodos.every((existingTodo, idx) => {
            const newTodo = newTodos[idx];
            return existingTodo.text === newTodo.text;
          });
        });

        if (existingTodoIndex !== -1) {
          // Update existing todo step instead of creating new one
          todoSteps[existingTodoIndex] = {
            ...step,
            parsed,
            originalIndex: index,
            id: todoSteps[existingTodoIndex].id, // Keep same ID
          };
          // Mark as seen to prevent duplicates (use a key based on task texts only)
          const todosTextKey = `todo-${JSON.stringify(
            parsed.todos.map((t) => t.text)
          )}`;
          seenContent.add(todosTextKey);
          return; // Don't add as new step
        }

        // Check for exact match (same todos with same completion status)
        const exactMatch = todoSteps.some(
          (s) =>
            JSON.stringify(
              s.parsed.todos.map((t) => ({
                text: t.text,
                completed: t.completed,
              }))
            ) === todosKey
        );
        if (exactMatch) {
          return;
        }
      }

      seenContent.add(contentKey);

      if (parsed.type === "reasoning") {
        // Only add reasoning if it has valid content
        if (parsed.content && parsed.content.trim().length > 0) {
          reasoningSteps.push({
            ...step,
            parsed,
            originalIndex: index,
            id: `reasoning-${index}-${step.timestamp || index}`,
          });
        }
      } else if (parsed.type === "todo") {
        todoSteps.push({
          ...step,
          parsed,
          originalIndex: index,
          id: `todo-${index}-${step.timestamp || index}`,
        });
      } else {
        // For text type steps, also add to reasoning if step.step === "Reasoning"
        // This handles edge cases where parseContent might miss it
        if (step.step && step.step.toLowerCase() === "reasoning") {
          // Only add if content is not empty
          if (step.content && step.content.trim().length > 0) {
            reasoningSteps.push({
              ...step,
              parsed: { type: "reasoning", content: step.content },
              originalIndex: index,
              id: `reasoning-${index}-${step.timestamp || index}`,
            });
          }
        }
      }
    });

    // Sort by timestamp or index to maintain order
    reasoningSteps.sort(
      (a, b) =>
        (a.timestamp || a.originalIndex) - (b.timestamp || b.originalIndex)
    );
    todoSteps.sort(
      (a, b) =>
        (a.timestamp || a.originalIndex) - (b.timestamp || b.originalIndex)
    );

    // Parse current step (no step name available for currentStep)
    const currentParsed = currentStep ? parseContent(currentStep, null) : null;

    // Calculate progress for a todo list
    const calculateProgress = (todos) => {
      const completed = todos.filter((t) => t.completed).length;
      const total = todos.length;
      return {
        completed,
        total,
        percentage: total > 0 ? (completed / total) * 100 : 0,
      };
    };

    // Toggle todo list expansion
    const toggleTodo = (index) => {
      setExpandedTodos((prev) => {
        const newSet = new Set(prev);
        if (newSet.has(index)) {
          newSet.delete(index);
        } else {
          newSet.add(index);
        }
        return newSet;
      });
    };

    // Filter out empty reasoning content
    const validReasoningSteps = reasoningSteps.filter(
      (step) => step.parsed.content && step.parsed.content.trim().length > 0
    );

    // Show container only if we have valid content
    const hasValidContent =
      todoSteps.length > 0 ||
      validReasoningSteps.length > 0 ||
      (currentStep && currentStep.trim().length > 0);

    if (!hasValidContent) return null;

    return (
      <div className="thinking-steps-container">
        {/* Reasoning Section - Only show reasoning, no tasks */}
        {validReasoningSteps.length > 0 && (
          <div className="thinking-section reasoning-section">
            <div className="section-header">
              <span className="section-icon">✨</span>
              <span className="section-title">Reasoning</span>
            </div>
            <div className="section-content reasoning-content-fixed">
              {validReasoningSteps.map((step) => (
                <div key={step.id} className="reasoning-item">
                  <div className="reasoning-text">{step.parsed.content}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function to prevent unnecessary re-renders
    // Only re-render if steps, isStreaming, or currentStep actually changed
    return (
      prevProps.isStreaming === nextProps.isStreaming &&
      prevProps.currentStep === nextProps.currentStep &&
      prevProps.steps.length === nextProps.steps.length &&
      prevProps.steps.every((step, index) => {
        const nextStep = nextProps.steps[index];
        return (
          step.step === nextStep.step &&
          step.content === nextStep.content &&
          step.id === nextStep.id
        );
      })
    );
  }
);

ThinkingStepsDisplay.displayName = "ThinkingStepsDisplay";

export default ThinkingStepsDisplay;
