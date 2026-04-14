
class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found in the agent's toolkits."""
    def __init__(self, *args):
        super().__init__(*args)


class ToolExecutionError(Exception):
    """Raised when a tool execution fails (e.g., command error, file not found).
    
    Attributes:
        tool_name: Name of the tool that failed
        tool_args: Arguments passed to the tool
        error_type: Classification of the error
        suggestion: Suggested action to fix the error
    """
    def __init__(self, message: str, tool_name: str = "", tool_args: dict = None, 
                 error_type: str = "unknown", suggestion: str = ""):
        super().__init__(message)
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self.error_type = error_type
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        """Convert error to dictionary for LLM consumption."""
        return {
            "error": str(self),
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "error_type": self.error_type,
            "suggestion": self.suggestion,
        }


class ToolTimeoutError(ToolExecutionError):
    """Raised when a tool execution times out."""
    def __init__(self, message: str, tool_name: str = "", tool_args: dict = None,
                 timeout_seconds: int = 0):
        super().__init__(
            message=message,
            tool_name=tool_name,
            tool_args=tool_args,
            error_type="timeout",
            suggestion=f"The operation timed out after {timeout_seconds}s. Try with a simpler query or increase timeout."
        )
        self.timeout_seconds = timeout_seconds


class ToolPermissionError(ToolExecutionError):
    """Raised when a tool fails due to permission issues."""
    def __init__(self, message: str, tool_name: str = "", tool_args: dict = None):
        super().__init__(
            message=message,
            tool_name=tool_name,
            tool_args=tool_args,
            error_type="permission",
            suggestion="Check file/directory permissions or run with elevated privileges if appropriate."
        )


class ToolValidationError(ToolExecutionError):
    """Raised when tool arguments fail validation."""
    def __init__(self, message: str, tool_name: str = "", tool_args: dict = None,
                 validation_errors: list = None):
        super().__init__(
            message=message,
            tool_name=tool_name,
            tool_args=tool_args,
            error_type="validation",
            suggestion="Check tool arguments against the schema and fix validation errors."
        )
        self.validation_errors = validation_errors or []


class ToolRetryableError(ToolExecutionError):
    """Raised when a tool fails but the operation might succeed on retry.
    
    Examples: network timeouts, temporary resource unavailability.
    """
    def __init__(self, message: str, tool_name: str = "", tool_args: dict = None,
                 max_retries: int = 3):
        super().__init__(
            message=message,
            tool_name=tool_name,
            tool_args=tool_args,
            error_type="retryable",
            suggestion=f"This error might be transient. Automatic retry will be attempted (max {max_retries} times)."
        )
        self.max_retries = max_retries
