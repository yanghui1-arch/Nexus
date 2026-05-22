
class ToolNotFoundError(Exception):
    def __init__(self, *args):
        """Initialize the object."""
        super().__init__(*args)
