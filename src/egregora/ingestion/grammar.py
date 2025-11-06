"""WhatsApp message grammar using pyparsing (MODERN - Phase 5).

This module defines a declarative grammar for WhatsApp message format parsing.
Replaces complex regex patterns with composable parser combinators.

Benefits over regex:
- Self-documenting (grammar is the specification)
- Composable (reuse sub-grammars)
- Type-safe (direct mapping to domain objects)
- Extensible (easy to add new formats)
- Testable (each rule tested independently)

Grammar supports multiple WhatsApp export formats:
- US format: "1/15/25, 2:30 PM - Author: Message"
- EU format: "15/01/2025, 14:30 - Author: Message"
- 24-hour time: "1/15/25, 14:30 - Author: Message"
- No date: "2:30 PM - Author: Message" (continuation from previous date)
"""

from pyparsing import (
    CaselessLiteral,
    Combine,
    Literal,
    Optional,
    ParserElement,
    Regex,
    Suppress,
    Word,
    alphanums,
    nums,
    one_of,
    rest_of_line,
)

# Enable packrat parsing for better performance
ParserElement.enablePackrat()


# Date components
def build_date_grammar() -> ParserElement:
    """Build date grammar supporting multiple formats.

    Supports:
    - US: 1/15/25, 1/15/2025
    - EU: 15/01/25, 15.01.2025
    - ISO: 2025-01-15

    Returns:
        Parser for date field
    """
    day = Word(nums, min=1, max=2)
    month = Word(nums, min=1, max=2)
    year = Word(nums, min=2, max=4)

    # Separator can be / or . or -
    sep = one_of("/ . -")

    # US format: month/day/year
    us_date = Combine(month + sep + day + sep + year)

    # EU format: day/month/year
    eu_date = Combine(day + sep + month + sep + year)

    # ISO format: year-month-day
    iso_date = Combine(year + Literal("-") + month + Literal("-") + day)

    return (iso_date | us_date | eu_date)("date")


def build_time_grammar() -> ParserElement:
    """Build time grammar supporting 12h and 24h formats.

    Supports:
    - 12h: "2:30 PM", "11:05 AM"
    - 24h: "14:30", "09:15"

    Returns:
        Parser for time field
    """
    hour = Word(nums, min=1, max=2)
    minute = Word(nums, exact=2)

    # Base time HH:MM
    time_base = Combine(hour + Literal(":") + minute)

    # AM/PM marker (optional)
    am_pm = CaselessLiteral("AM") | CaselessLiteral("PM")

    # Complete time with optional AM/PM
    time_field = time_base("time") + Optional(am_pm)("ampm")

    return time_field


def build_separator_grammar() -> ParserElement:
    """Build separator grammar (between timestamp and author).

    WhatsApp uses various separators:
    - Em dash: —
    - Hyphen: -

    Returns:
        Parser that consumes separator
    """
    return Suppress(Regex(r"[—\-]"))


def build_author_grammar() -> ParserElement:
    """Build author name grammar.

    Author is everything from separator to colon.
    Can include spaces, unicode, special chars.

    Returns:
        Parser for author field
    """
    # Match everything except colon
    # Use negative lookahead to stop before ':'
    author = Regex(r"[^:]+")("author")
    return author


def build_message_grammar() -> ParserElement:
    """Build message text grammar.

    Message is everything after the colon to end of line.

    Returns:
        Parser for message field
    """
    return rest_of_line("message")


def build_whatsapp_message_grammar() -> ParserElement:
    """Build complete WhatsApp message line grammar.

    Format: [DATE, ]TIME [AM/PM] - AUTHOR: MESSAGE

    Examples:
    - "1/15/25, 2:30 PM - John: Hello!"
    - "14:30 - Alice: How are you?"
    - "15/01/2025, 09:15 - Bob: Good morning"

    Returns:
        Complete parser for WhatsApp message lines
    """
    date = build_date_grammar()
    time = build_time_grammar()
    separator = build_separator_grammar()
    author = build_author_grammar()
    message = build_message_grammar()

    # Optional comma or space after date
    date_sep = Optional(Suppress(Literal(",")) | Suppress(Literal(" ")))

    # Complete grammar
    grammar = (
        Optional(date + date_sep)  # Date is optional (continuation lines)
        + time                      # Time is required
        + Optional(Suppress(" "))   # Optional space before separator
        + separator                 # Separator (- or —)
        + Optional(Suppress(" "))   # Optional space after separator
        + author                    # Author name
        + Suppress(Literal(":"))    # Colon separator
        + Optional(Suppress(" "))   # Optional space after colon
        + message                   # Message text
    )

    return grammar


# Create the main grammar instance
WHATSAPP_MESSAGE_GRAMMAR = build_whatsapp_message_grammar()


def parse_whatsapp_line(line: str) -> dict[str, str] | None:
    """Parse a single WhatsApp message line.

    Args:
        line: Raw line from WhatsApp export

    Returns:
        Dict with parsed fields (date, time, ampm, author, message) or None if not a message line

    Examples:
        >>> parse_whatsapp_line("1/15/25, 2:30 PM - John: Hello!")
        {'date': '1/15/25', 'time': '2:30', 'ampm': 'PM', 'author': 'John', 'message': 'Hello!'}

        >>> parse_whatsapp_line("This is a continuation")
        None
    """
    try:
        result = WHATSAPP_MESSAGE_GRAMMAR.parseString(line, parseAll=True)
        return result.asDict()
    except Exception:
        # Not a message line (continuation or empty)
        return None


__all__ = [
    "build_whatsapp_message_grammar",
    "parse_whatsapp_line",
    "WHATSAPP_MESSAGE_GRAMMAR",
]
