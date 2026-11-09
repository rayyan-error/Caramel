"""
Dynamic Web Search Query Parser & URL Generator for Project Caramel / Uranus.
Handles Google and YouTube search query extraction, parameter encoding via urllib,
and dynamic CommandDefinition construction.
"""

from dataclasses import dataclass
import re
from typing import Optional
import urllib.parse

from config.settings import CommandDefinition


@dataclass(frozen=True)
class SearchResult:
    """Structured information extracted from a spoken search command."""
    engine: str            # 'google' or 'youtube'
    query: str             # Normalized search query terms
    new_window: bool       # Whether to open in a new window
    url: str               # Fully encoded search URL


# Pre-compiled regular expressions for fast query parsing
_RE_LEADING_TRIGGER = re.compile(r"^(?:search\s+for|search|look\s+up|find)\b\s*")
_RE_LEADING_ENGINE = re.compile(
    r"^(?:(?:on|in|from|via)\s+(youtube|google)(?:\s+for)?|(youtube|google)\s+for)\b\s*"
)
_RE_TRAILING_ENGINE = re.compile(r"\s+\b(?:on|in|from|via)\s+(youtube|google)\s*$")
_RE_BARE_TRAILING_ENGINE = re.compile(r"\s+\b(youtube|google)\s*$")
_RE_LEADING_FOR = re.compile(r"^for\s+")
_RE_DANGLE_PREFIX = re.compile(r"^(?:on|for)\s+")
_RE_DANGLE_SUFFIX = re.compile(r"\s+(?:on|for)$")


def parse_search_query(text: str) -> Optional[SearchResult]:
    """
    Parses a spoken or text search instruction and produces a SearchResult.
    Supports:
        - "search <query>" (defaults to Google)
        - "search <query> on google"
        - "search <query> on youtube"
        - "search on google for <query>"
        - "search on youtube for <query>"
        - "search for <query> on google"
        - "search for <query> on youtube"
        - "... in a new window" (for any of the above)
    Returns None if text does not represent a valid search query with payload terms.
    """
    raw = text.strip()
    if not raw:
        return None

    lower = raw.lower().replace("[unk]", " ")
    lower = " ".join(lower.split())
    if not lower:
        return None

    # 1. Detect and strip new window request
    new_window = False
    if "in a new window" in lower:
        new_window = True
        lower = lower.replace("in a new window", " ")
    elif "new window" in lower:
        new_window = True
        lower = lower.replace("new window", " ")

    lower = " ".join(lower.split())

    # 2. Strip leading search initiation trigger ("search for", "search", "look up", "find")
    lower = _RE_LEADING_TRIGGER.sub("", lower).strip()
    if not lower:
        return None

    # 3. Determine target search engine (YouTube vs Google default) from prefix or suffix
    # Checking suffix first handles queries like "search youtube api on google" accurately.
    engine = "google"
    engine_matched = False

    m_trail = _RE_TRAILING_ENGINE.search(lower)
    if m_trail:
        engine = m_trail.group(1)
        lower = lower[:m_trail.start()].strip()
        engine_matched = True

    if not engine_matched:
        m_lead = _RE_LEADING_ENGINE.match(lower)
        if m_lead:
            engine = m_lead.group(1) or m_lead.group(2)
            lower = lower[m_lead.end():].strip()
            engine_matched = True

    if not engine_matched:
        m_bare = _RE_BARE_TRAILING_ENGINE.search(lower)
        if m_bare:
            engine = m_bare.group(1)
            lower = lower[:m_bare.start()].strip()

    # 4. Strip leading "for " if remaining (e.g. "search on google for <query>")
    lower = _RE_LEADING_FOR.sub("", lower).strip()
    query = _RE_DANGLE_PREFIX.sub("", lower).strip()
    query = _RE_DANGLE_SUFFIX.sub("", query).strip()
    query = " ".join(query.split())

    if not query:
        return None

    # 5. Format target URL using RFC 3986 / application/x-www-form-urlencoded
    encoded_query = urllib.parse.quote_plus(query)
    if engine == "youtube":
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
    else:
        url = f"https://www.google.com/search?q={encoded_query}"

    return SearchResult(
        engine=engine,
        query=query,
        new_window=new_window,
        url=url
    )


def create_search_command(search_result: SearchResult, phrase: str = "") -> CommandDefinition:
    """Builds a dynamic CommandDefinition for a parsed search query."""
    engine_id = search_result.engine.upper()
    win_suffix = "_NEW_WINDOW" if search_result.new_window else ""
    command_id = f"CMD_SEARCH_{engine_id}{win_suffix}"

    return CommandDefinition(
        command_id=command_id,
        phrase=phrase or f"search {search_result.query} on {search_result.engine}",
        action_type="OPEN_URL",
        target_app="brave",
        new_window=search_result.new_window,
        url=search_result.url,
        extra_params={
            "query": search_result.query,
            "engine": search_result.engine
        }
    )
