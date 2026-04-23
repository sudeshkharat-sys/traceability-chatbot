"""
Custom Exception Classes
"""


class DatabaseConnectionError(Exception):
    """Raised when database connection fails"""

    pass


class QueryExecutionError(Exception):
    """Raised when query execution fails"""

    pass


class AgentInitializationError(Exception):
    """Raised when agent initialization fails"""

    pass


class ConversationNotFoundError(Exception):
    """Raised when conversation is not found"""

    pass


class InvalidAgentTypeError(Exception):
    """Raised when invalid agent type is specified"""

    pass
