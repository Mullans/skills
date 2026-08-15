"""Shared exceptions for mark2word."""


class Mark2WordError(Exception):
    """Base error for mark2word conversion failures."""


class FrontmatterError(Mark2WordError, ValueError):
    """Invalid or unsupported YAML frontmatter."""


class RegionError(Mark2WordError, ValueError):
    """Unbalanced or invalid region markers."""

    def __init__(self, message: str, line_no: int | None = None):
        self.line_no = line_no
        if line_no is None:
            super().__init__(message)
        else:
            super().__init__(f"line {line_no}: {message}")


class ThemeError(Mark2WordError, ValueError):
    """Invalid theme configuration or inheritance."""


class ParseError(Mark2WordError, ValueError):
    """Invalid markdown structure."""

    def __init__(self, message: str, line_no: int | None = None):
        self.line_no = line_no
        if line_no is None:
            super().__init__(message)
        else:
            super().__init__(f"line {line_no}: {message}")


class ImageError(Mark2WordError, ValueError):
    """Missing or unreadable image reference."""

    def __init__(self, message: str, line_no: int | None = None):
        self.line_no = line_no
        if line_no is None:
            super().__init__(message)
        else:
            super().__init__(f"line {line_no}: {message}")
