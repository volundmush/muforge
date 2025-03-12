from rich.markup import MarkupError
from rich.text import Text

def rich_text(value: str):
    try:
        Text.from_markup(value)
    except MarkupError:
        raise ValueError("Invalid markup")
    return value

def optional_rich_text(value: str | None) -> str | None:
    if value is None:
        return None
    return rich_text(value)

def user_rich_text(text: str) -> str:
    """
    Args:
        text (str): The text to validate.

    Returns:
        text (str): The validated text with literal "\n" and "\t" replaced with
                    actual newlines and indents, and escaped slashes converted appropriately.

    Raises:
        ValueError: If the text is invalid.
    """

    # First, convert literal escape sequences to their actual characters.
    # This approach leverages Python's 'unicode_escape' decoding.
    try:
        # This will turn a string like "Hello\\nWorld\\tTest\\\\Done" into:
        # "Hello\nWorld\tTest\Done"
        processed = text.encode("utf-8").decode("unicode_escape")
    except Exception as e:
        raise ValueError(f"Error decoding escape sequences: {e}")

    return rich_text(processed)

def optional_user_rich_text(value: str | None) -> str | None:
    if value is None:
        return None
    return user_rich_text(value)