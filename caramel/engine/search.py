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

    lower = raw.lower()

    # 1. Detect and strip new window request
    new_window = False
    if "in a new window" in lower:
        new_window = True
        lower = lower.replace("in a new window", " ")
    elif "new window" in lower:
        new_window = True
        lower = lower.replace("new window", " ")

    # 2. Determine target search engine (YouTube vs Google default)
    engine = "google"
    if "youtube" in lower:
        engine = "youtube"
        lower = re.sub(r"\b(on|in|from|via)?\s*youtube\b", " ", lower)
    elif "google" in lower:
        engine = "google"
        lower = re.sub(r"\b(on|in|from|via)?\s*google\b", " ", lower)

    # 3. Strip search initiation trigger keywords
    lower = re.sub(r"^(search\s+for|search|look\s+up|find)\s*", " ", lower)
    lower = re.sub(r"^for\s+", " ", lower)

    # 4. Clean extra spaces and normalize query terms, stripping any [unk] tokens
    lower = lower.replace("[unk]", " ")
    query = " ".join(lower.split())
    if not query:
        return None

    # Strip any trailing/leading preposition fragments if left behind
    query = re.sub(r"^(on|for|in|about)\s+", "", query).strip()
    query = re.sub(r"\s+(on|for|in)$", "", query).strip()

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
