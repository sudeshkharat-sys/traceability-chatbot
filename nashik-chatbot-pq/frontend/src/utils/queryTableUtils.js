/**
 * Extracts a structured issue table from a QLense response.
 *
 * The LLM is asked to emit its Phase 1 issue list as a fenced ```json
 * code block (an array of row objects) rather than a markdown pipe table,
 * because streamed markdown tables have proven unreliable (the model
 * frequently drops the newline between rows, producing unparseable text).
 * JSON is far more robustly generated and parsed.
 *
 * This strips that code block out of the display text (so it isn't shown
 * twice) and returns the parsed rows for rendering as a real HTML table.
 */

const JSON_BLOCK_RE = /```json\s*([\s\S]*?)```/i;

export function extractQueryResultsTable(text) {
  if (!text) return { rows: null, strippedText: text };

  const match = text.match(JSON_BLOCK_RE);
  if (!match) return { rows: null, strippedText: text };

  try {
    const parsed = JSON.parse(match[1].trim());
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return { rows: null, strippedText: text };
    }
    const strippedText = (text.slice(0, match.index) + text.slice(match.index + match[0].length)).trim();
    return { rows: parsed, strippedText };
  } catch (e) {
    // Malformed/incomplete JSON (e.g. still streaming) — fall back to
    // showing the raw text as-is rather than crashing the render.
    return { rows: null, strippedText: text };
  }
}
