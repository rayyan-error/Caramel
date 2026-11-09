"""
Deterministic Trie-based Prefix Ambiguity Resolver and Command Matcher.
Enforces strict zero-guessing command validation and solves prefix collisions.
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple

from config.settings import CommandDefinition


class MatchResult(Enum):
    EXACT_MATCH = "EXACT_MATCH"    # Reached a terminal registered command
    PREFIX_ONLY = "PREFIX_ONLY"    # Valid prefix of a longer command, but not terminal
    UNKNOWN = "UNKNOWN"            # Diverged from all registered paths, or empty / invalid


class TrieNode:
    """Node in the command prefix tree."""
    __slots__ = ("children", "is_terminal", "command")

    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_terminal: bool = False
        self.command: Optional[CommandDefinition] = None


class CommandTrie:
    """
    Deterministic Trie storing tokenized command sequences.
    Distinguishes exact matches, partial prefixes, and unknown paths.
    """
    def __init__(self):
        self.root = TrieNode()

    def insert(self, phrase: str, command: CommandDefinition) -> None:
        """Insert a normalized command phrase into the Trie."""
        words = phrase.strip().lower().split()
        if not words:
            return

        current = self.root
        for word in words:
            if word not in current.children:
                current.children[word] = TrieNode()
            current = current.children[word]

        current.is_terminal = True
        current.command = command

    def match(self, utterance: str) -> Tuple[MatchResult, Optional[CommandDefinition]]:
        """
        Evaluate a complete or partial utterance against the Trie.
        Returns:
            (MatchResult, CommandDefinition or None)
        """
        words = utterance.strip().lower().split()
        if not words:
            return MatchResult.UNKNOWN, None

        current = self.root
        for word in words:
            # If word is unknown or [unk], path diverges immediately
            if word not in current.children:
                return MatchResult.UNKNOWN, None
            current = current.children[word]

        if current.is_terminal:
            return MatchResult.EXACT_MATCH, current.command
        else:
            return MatchResult.PREFIX_ONLY, None
