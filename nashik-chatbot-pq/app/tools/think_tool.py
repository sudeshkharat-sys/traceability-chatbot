"""
Think Tool for Agent Reasoning
Allows agents to pause and reason through problems, especially after tool calls
"""

import logging
from typing import Dict, Any
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def think(thought: str) -> None:
    """
    CRITICAL TOOL: Use this tool to think through problems before taking action.

    You MUST use this tool:
    1. BEFORE executing your first query - to plan your approach
    2. AFTER receiving query results - to analyze the data
    3. BEFORE generating your final response - to verify completeness

    This tool helps you:
    - Plan your analysis approach
    - Analyze query results before responding
    - Verify you have all required information
    - Re-evaluate when new information comes in
    - Ensure your response is complete and accurate
    - Check if data is suitable for visualization

    Use this tool as a scratchpad to:
    - Outline progress until now
    - Outline a way forward
    - Justify the way forward (and address any apparent mistakes)
    - Outline the next steps
    - Re-evaluate after receiving tool results
    - Plan before taking action
    - **Consider if query results should have a chart visualization**
    - **If charts are appropriate, plan a descriptive chart title**

    CHART VISUALIZATION REMINDER:
    - When results show trends, distributions, or comparisons, charts will be auto-generated
    - You MUST include a chart title in your response: **Chart: [Title]**
    - Make titles specific: "Monthly Defect Trend - Q1 2025" not "Trend Chart"
    - Include context: time periods, zones, categories mentioned in query
    - Keep titles 5-10 words, professional and descriptive

    Args:
        thought: A thought to think about. Should include:
            - Current situation/context
            - What has been done so far
            - What information is available
            - What needs to be done next
            - Any concerns or edge cases to consider
            - Analysis of query results (if applicable)
            - Whether data is suitable for charts and what title to use

    Returns:
        None (thought is captured from the tool call arguments, not the return value)
    """
    # Log the thought for debugging/monitoring
    logger.info(f"🤔 Agent thinking: {thought}")
    logger.info(f"🤔 Full thought ({len(thought)} chars): {thought}")

    # We don't need to return anything - the thought is in the tool call arguments
    # and will be captured from there in the streaming code
    return None
