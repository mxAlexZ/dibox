from .resolution_stack import ResolutionStack, format_frame


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

        requested_type, name = self.resolution_stack[-1]

        formatted_stack = [f"- {format_frame(requested_type, name)}  <-- failure"]
        formatted_stack += [
            f"- {format_frame(t, n)}"
            for t, n in reversed(self.resolution_stack[:-1])
        ]
        formatted_stack_str = "\n".join(formatted_stack)
        message = (
            f"Can't resolve ({format_frame(requested_type, name)}).\n"
            f"Reason: {reason}.\n"
            f"Resolution path:\n{formatted_stack_str}"
        )
        super().__init__(message)
