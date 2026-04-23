"""
Chart Data Formatter Utility

This module provides utilities to format Neo4j query results and other data
into chart-ready formats for the frontend ChartComponent.
"""

from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


ChartType = Literal["bar", "line", "pie"]


class ChartFormatter:
    """Formats data into chart-compatible structures"""

    @staticmethod
    def format_chart_data(
        chart_type: ChartType,
        data: List[Dict[str, Any]],
        title: str,
        x_axis: Optional[str] = None,
        y_axis: Optional[List[str]] = None,
        name_key: Optional[str] = None,
        value_key: Optional[str] = None,
        colors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Format data into chart configuration structure.

        Args:
            chart_type: Type of chart ('bar', 'line', or 'pie')
            data: List of data points/records
            title: Chart title
            x_axis: Key for x-axis (for bar/line charts)
            y_axis: List of keys for y-axis values (for bar/line charts)
            name_key: Key for category names (for pie charts)
            value_key: Key for values (for pie charts)
            colors: Optional list of color hex codes

        Returns:
            Dictionary with chart configuration
        """
        chart_config = {
            "type": chart_type,
            "title": title,
            "data": data,
            "config": {},
        }

        if chart_type in ["bar", "line"]:
            if x_axis:
                chart_config["config"]["xAxis"] = x_axis
            if y_axis:
                chart_config["config"]["yAxis"] = y_axis
        elif chart_type == "pie":
            if name_key:
                chart_config["config"]["nameKey"] = name_key
            if value_key:
                chart_config["config"]["valueKey"] = value_key

        if colors:
            chart_config["config"]["colors"] = colors

        return chart_config

    @staticmethod
    def format_time_series(
        records: List[Dict[str, Any]],
        time_key: str,
        value_keys: List[str],
        title: str,
        chart_type: ChartType = "line",
    ) -> Dict[str, Any]:
        """
        Format time series data for line or bar charts.

        Args:
            records: List of records with time and value data
            time_key: Key containing time/date information
            value_keys: Keys for values to plot
            title: Chart title
            chart_type: 'line' or 'bar'

        Returns:
            Chart configuration dictionary
        """
        # Sort by time if possible
        try:
            sorted_records = sorted(records, key=lambda x: x.get(time_key, ""))
        except:
            sorted_records = records

        return ChartFormatter.format_chart_data(
            chart_type=chart_type,
            data=sorted_records,
            title=title,
            x_axis=time_key,
            y_axis=value_keys,
        )

    @staticmethod
    def format_distribution(
        records: List[Dict[str, Any]],
        name_key: str,
        value_key: str,
        title: str,
        chart_type: ChartType = "pie",
    ) -> Dict[str, Any]:
        """
        Format distribution data for pie or bar charts.

        Args:
            records: List of records with categories and values
            name_key: Key for category names
            value_key: Key for values
            title: Chart title
            chart_type: 'pie' or 'bar'

        Returns:
            Chart configuration dictionary
        """
        if chart_type == "pie":
            return ChartFormatter.format_chart_data(
                chart_type="pie",
                data=records,
                title=title,
                name_key=name_key,
                value_key=value_key,
            )
        else:  # bar chart
            return ChartFormatter.format_chart_data(
                chart_type="bar",
                data=records,
                title=title,
                x_axis=name_key,
                y_axis=[value_key],
            )

    @staticmethod
    def format_comparison(
        records: List[Dict[str, Any]],
        category_key: str,
        compare_keys: List[str],
        title: str,
        chart_type: ChartType = "bar",
    ) -> Dict[str, Any]:
        """
        Format comparison data for bar or line charts.

        Args:
            records: List of records with categories and comparison values
            category_key: Key for category names
            compare_keys: Keys for values to compare
            title: Chart title
            chart_type: 'bar' or 'line'

        Returns:
            Chart configuration dictionary
        """
        return ChartFormatter.format_chart_data(
            chart_type=chart_type,
            data=records,
            title=title,
            x_axis=category_key,
            y_axis=compare_keys,
        )

    @staticmethod
    def detect_chart_type_from_data(
        data: List[Dict[str, Any]], user_question: str = ""
    ) -> Optional[ChartType]:
        """
        Intelligently detect the best chart type based on data structure and user question.

        Args:
            data: Data records
            user_question: User's question (for context)

        Returns:
            Suggested chart type or None
        """
        if not data or len(data) == 0:
            return None

        question_lower = user_question.lower()

        # Keywords suggesting specific chart types
        if any(
            keyword in question_lower
            for keyword in ["trend", "over time", "timeline", "progression"]
        ):
            return "line"

        if any(
            keyword in question_lower
            for keyword in [
                "distribution",
                "breakdown",
                "percentage",
                "proportion",
                "share",
            ]
        ):
            return "pie"

        if any(
            keyword in question_lower
            for keyword in ["compare", "comparison", "vs", "versus", "difference"]
        ):
            return "bar"

        # Analyze data structure
        first_record = data[0]
        keys = list(first_record.keys())

        # Check for time-related keys
        time_keys = ["date", "time", "month", "year", "quarter", "week", "day"]
        has_time_key = any(
            any(tk in key.lower() for tk in time_keys) for key in keys
        )

        if has_time_key:
            return "line"

        # If only 2 keys (name + value), likely a distribution
        if len(keys) == 2:
            return "pie"

        # Default to bar chart for multi-value comparisons
        return "bar"

    @staticmethod
    def should_generate_chart(user_question: str, query_results: List[Dict]) -> bool:
        """
        Determine if a chart should be generated based on the question and results.

        Args:
            user_question: User's question
            query_results: Query results from Neo4j

        Returns:
            True if chart should be generated
        """
        if not query_results or len(query_results) == 0:
            return False

        # Too much data might not be suitable for charts
        if len(query_results) > 50:
            return False

        question_lower = user_question.lower()

        # Chart-related keywords (high priority - explicit chart requests)
        explicit_chart_keywords = [
            "chart",
            "graph",
            "plot",
            "visualize",
            "visualization",
        ]

        # Chart-related keywords (medium priority)
        chart_keywords = [
            "show",
            "display",
            "trend",
            "distribution",
            "comparison",
            "compare",
            "over time",
            "breakdown",
            "percentage",
            "rate",
            "count",
            "number of",
            "how many",
            "statistics",
            "metrics",
        ]

        # Questions that don't need charts
        non_chart_keywords = [
            "what is",
            "who is",
            "when was",
            "where is",
            "list all",
            "show me all",
            "explain",
            "describe",
            "tell me about",
        ]

        # If user explicitly asks for chart/plot/graph - ALWAYS generate
        has_explicit_chart = any(keyword in question_lower for keyword in explicit_chart_keywords)
        if has_explicit_chart:
            return True

        # Check if question suggests a chart
        has_chart_keyword = any(keyword in question_lower for keyword in chart_keywords)
        has_non_chart = any(keyword in question_lower for keyword in non_chart_keywords)

        if has_chart_keyword and not has_non_chart:
            return True

        # Check if data is numeric (good for charts)
        first_record = query_results[0]
        numeric_fields = sum(
            1
            for value in first_record.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )

        # If multiple numeric fields, likely good for charting
        if numeric_fields >= 1 and len(query_results) >= 2:
            return True

        return False


def _extract_chart_title_from_response(user_question: str) -> Optional[str]:
    """
    Extract chart title from agent's response if it follows the pattern:
    **Chart: [Title]**

    Args:
        user_question: The user's question or agent's response text

    Returns:
        Extracted title or None if not found
    """
    import re

    # Look for pattern: **Chart: [Title]** or **Chart:[Title]**
    pattern = r'\*\*Chart:\s*([^\*]+?)\*\*'
    match = re.search(pattern, user_question, re.IGNORECASE)

    if match:
        title = match.group(1).strip()
        return title

    return None


def _generate_chart_title(chart_type: str, x_key: str, y_keys: List[str], data: List[Dict]) -> str:
    """
    Generate a descriptive chart title based on data structure.
    This is a fallback when agent doesn't provide a title.

    Args:
        chart_type: Type of chart ('line', 'bar', 'pie')
        x_key: Key for x-axis or category
        y_keys: Keys for y-axis values
        data: The data being charted

    Returns:
        Descriptive title string
    """
    # Format key names nicely (remove underscores, capitalize)
    def format_key(key):
        return key.replace('_', ' ').replace('-', ' ').title()

    if chart_type == "line":
        if len(y_keys) == 1:
            return f"{format_key(y_keys[0])} Over {format_key(x_key)}"
        else:
            return f"{', '.join([format_key(k) for k in y_keys[:2]])} Trend"
    elif chart_type == "bar":
        if len(y_keys) == 1:
            return f"{format_key(y_keys[0])} by {format_key(x_key)}"
        else:
            return f"Comparison: {', '.join([format_key(k) for k in y_keys[:2]])}"
    elif chart_type == "pie":
        if len(y_keys) >= 1:
            return f"{format_key(y_keys[0])} Distribution"
        else:
            return f"{format_key(x_key)} Distribution"

    return "Data Visualization"


def _generate_axis_labels(x_key: str, y_keys: List[str]) -> tuple:
    """
    Generate descriptive axis labels.

    Args:
        x_key: Key for x-axis
        y_keys: Keys for y-axis values

    Returns:
        Tuple of (x_label, y_label)
    """
    def format_key(key):
        return key.replace('_', ' ').replace('-', ' ').title()

    x_label = format_key(x_key)

    if len(y_keys) == 1:
        y_label = format_key(y_keys[0])
    elif len(y_keys) > 1:
        # If multiple y-axes, use generic label or first key
        y_label = format_key(y_keys[0])
    else:
        y_label = "Value"

    return x_label, y_label


def format_neo4j_results_for_chart(
    results: List[Dict[str, Any]], user_question: str
) -> Optional[Dict[str, Any]]:
    """
    High-level function to automatically format Neo4j results into chart data.

    Args:
        results: Query results from Neo4j
        user_question: User's original question

    Returns:
        Chart configuration dict or None if no chart should be generated
    """
    if not ChartFormatter.should_generate_chart(user_question, results):
        return None

    # Detect chart type
    chart_type = ChartFormatter.detect_chart_type_from_data(results, user_question)
    if not chart_type:
        return None

    # Extract keys from first record
    if not results:
        return None

    first_record = results[0]
    keys = list(first_record.keys())

    # Find likely keys for axes
    time_keys = ["date", "time", "month", "year", "quarter", "week", "day"]
    category_keys = [
        "category", "type", "name", "status", "label", "zone", "part",
        "complaint", "issue", "failure", "defect", "problem",
        "model", "description", "desc", "vendor", "supplier",
        "dealer", "commodity", "plant", "batch", "region",
    ]

    x_key = None
    y_keys = []
    name_key = None
    value_key = None

    for key in keys:
        key_lower = key.lower()
        value = first_record[key]
        is_numeric = isinstance(value, (int, float)) and not isinstance(value, bool)

        # Check for time keys
        if any(tk in key_lower for tk in time_keys):
            x_key = key
        # Numeric values always go to y-axis (even if key name matches category_keys
        # e.g., "failure_count" contains "failure" but is numeric → y-axis)
        elif is_numeric:
            y_keys.append(key)
            if not value_key:
                value_key = key
        # Check for category keys (only for non-numeric string values)
        elif any(ck in key_lower for ck in category_keys):
            if not x_key:
                x_key = key
            name_key = key

    # Default to first non-numeric key if no x_key found
    if not x_key and keys:
        for key in keys:
            if not isinstance(first_record.get(key), (int, float, bool)):
                x_key = key
                name_key = key
                break
        if not x_key:
            x_key = keys[0]
            name_key = keys[0]

    # Prefer "name" keys over "no/code" keys for x-axis (more readable labels)
    # e.g., "HEAD LAMP ASSY RH (HIGH)" is better than "1701AW500091N" on x-axis
    if name_key and name_key != x_key and 'name' in name_key.lower():
        x_key = name_key

    # If x_key has all identical values (e.g., base_model='THAR ROXX' for every row),
    # find a better key with more unique values to use as x-axis
    if x_key and len(results) > 1:
        unique_x_values = set(str(r.get(x_key, '')) for r in results)
        if len(unique_x_values) <= 1:
            # Current x_key is constant - find a string key with more variety
            for key in keys:
                if key == x_key or key in y_keys:
                    continue
                if not isinstance(first_record.get(key), (int, float, bool)):
                    alt_unique = set(str(r.get(key, '')) for r in results)
                    if len(alt_unique) > 1:
                        x_key = key
                        name_key = key
                        break

    # Context-aware y-key filtering: when question is about failures/claims,
    # exclude process capability metrics (cp, cpk) from chart y-axis
    question_lower = user_question.lower()
    capability_fields = [k for k in y_keys if k.lower() in ('cp', 'cpk')]
    count_fields = [k for k in y_keys if any(
        w in k.lower() for w in ['count', 'failure', 'failed', 'claim',
                                   'incident', 'rejection', 'concern', 'qty',
                                   'produced', 'sample']
    )]
    if count_fields and capability_fields:
        # Only keep cp/cpk if user explicitly asks about capability
        if not any(w in question_lower for w in ['cp', 'cpk', 'capability', 'process capability']):
            y_keys = [k for k in y_keys if k not in capability_fields]

    # Try to extract title from user's question/response first
    # The user_question might contain agent's response with chart title
    extracted_title = _extract_chart_title_from_response(user_question)

    # Use extracted title if available, otherwise generate one
    if extracted_title:
        title = extracted_title
    else:
        # Fallback: Generate descriptive title based on data structure
        title = _generate_chart_title(chart_type, x_key, y_keys, results)

    # Generate axis labels
    x_label, y_label = _generate_axis_labels(x_key, y_keys)

    # Format based on chart type
    if chart_type == "pie":
        chart_config = ChartFormatter.format_distribution(
            records=results,
            name_key=name_key or x_key,
            value_key=value_key or (y_keys[0] if y_keys else keys[1]),
            title=title,
            chart_type="pie",
        )
    elif chart_type == "line":
        chart_config = ChartFormatter.format_time_series(
            records=results,
            time_key=x_key,
            value_keys=y_keys if y_keys else [keys[1]],
            title=title,
            chart_type="line",
        )
        # Add axis labels
        chart_config["config"]["xAxisLabel"] = x_label
        chart_config["config"]["yAxisLabel"] = y_label
        return chart_config
    else:  # bar
        chart_config = ChartFormatter.format_comparison(
            records=results,
            category_key=x_key,
            compare_keys=y_keys if y_keys else [keys[1]],
            title=title,
            chart_type="bar",
        )
        # Add axis labels
        chart_config["config"]["xAxisLabel"] = x_label
        chart_config["config"]["yAxisLabel"] = y_label
        return chart_config

    return chart_config
