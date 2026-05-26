from .resolution_stack import ResolutionStack, format_frame, format_resolution_path


class ResolutionError(Exception):
    """Raised when DIBox cannot resolve a requested dependency.

    Attributes:
        resolution_stack: Raw copy of the resolution stack at failure time.
            Each item is ``(requested_type, argument_name)``.
        reason: Human-readable reason for the resolution failure.
    """

    def __init__(self, reason: str, resolution_stack: ResolutionStack) -> None:
        self.resolution_stack: ResolutionStack = list(resolution_stack)
        self.reason = reason
        requested_type, name = resolution_stack[-1]
        message = (
            f"Can't resolve ({format_frame(requested_type, name)}).\n"
            f"Reason: {reason}.\n"
            f"Resolution path:\n{format_resolution_path(resolution_stack)}"
        )
        super().__init__(message)
