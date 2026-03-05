import re

import lark
from rich.markup import MarkupError
from rich.text import Text

import muforge


class NameSanitizer:
    RE_ALLOWED = re.compile(r"^[ \.'`a-zA-Z0-9_-]+$")

    def __init__(
        self, value_name: str, min_length: int = 1, max_length: int = 40
    ) -> None:
        self.value_name = value_name
        self.min_length = min_length
        self.max_length = max_length

    def __call__(self, value: str) -> str:
        if not value.strip():
            raise ValueError(f"{self.value_name} cannot be empty")
        if value.startswith(" ") or value.endswith(" "):
            raise ValueError(f"{self.value_name} cannot start or end with a space")
        if len(value) > self.max_length:
            raise ValueError(
                f"{self.value_name} cannot exceed {self.max_length} characters"
            )
        if len(value) < self.min_length:
            raise ValueError(
                f"{self.value_name} must be at least {self.min_length} characters"
            )
        if "\r" in value or "\n" in value or "\t" in value:
            raise ValueError(
                f"{self.value_name} cannot contain newline or tab characters"
            )
        if "  " in value:
            raise ValueError(f"{self.value_name} cannot contain consecutive spaces")
        if not self.RE_ALLOWED.match(value):
            raise ValueError(
                f"{self.value_name} can only contain alphanumeric characters, spaces, and the following punctuation: ' . ` _ -"
            )
        return value


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


def _validate_lock_funcs(lock: lark.Tree):
    """
    Given a lark tree, validate all of the lock_funcs in the tree.
    If any don't exist, raise an HTTP_400_BAD_REQUEST.
    """
    for node in lock.iter_subtrees():
        if node.data == "function_call":
            func_name = node.children[0].value
            if func_name not in muforge.LOCKFUNCS:
                raise ValueError(f"Unknown lock function: {func_name}")


def _validate_lock(access_type: str, lock: str):
    if lock in muforge.LOCK_CACHE:
        return muforge.LOCK_CACHE[lock]
    try:
        parsed = muforge.LOCKPARSER.parse(lock)
        _validate_lock_funcs(parsed)
        muforge.LOCK_CACHE[lock] = parsed
        return parsed
    except lark.LarkError as e:
        raise ValueError(f"Invalid lock syntax for access_type {access_type}: {e}")
    except ValueError as e:
        raise ValueError(f"Invalid lock syntax for access_type {access_type}: {e}")


def locks(value: dict[str, str]) -> dict[str, str]:
    out = dict()
    for access_type, lock in value.items():
        access = access_type.strip().lower()
        if not access:
            raise ValueError("Access type cannot be empty or whitespace.")
        if not lock:
            raise ValueError(f"Lock for access_type {access} cannot be empty.")
        if " " in access:
            raise ValueError(f"Access type {access} cannot contain spaces.")
        _validate_lock(access_type, lock)
        out[access] = lock
    return out


def optional_locks(value: dict[str, str] | None) -> dict[str, str] | None:
    if value is None:
        return None
    return locks(value)
