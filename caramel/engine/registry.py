"""
Command Registry for Project Caramel / Uranus.
Maintains all active command definitions and builds the prefix tree.
"""

from typing import Dict, List, Optional, Tuple

from config.settings import CommandDefinition, config
from caramel.engine.trie import CommandTrie, MatchResult
from caramel.engine.search import parse_search_query, create_search_command


class CommandRegistry:
    """
    Central registry that holds registered commands and compiles
    them into a deterministic prefix tree. Also resolves dynamic search intents.
    """
    def __init__(self, commands: Optional[List[CommandDefinition]] = None):
        self._commands: Dict[str, CommandDefinition] = {}
        self.trie = CommandTrie()
        
        command_list = commands if commands is not None else config.COMMANDS
        for cmd in command_list:
            self.register(cmd)

    def register(self, command: CommandDefinition) -> None:
        """Register a command, its explicit phrase aliases, and acoustic expansions into the Trie."""
        self._commands[command.command_id] = command
        phrases_to_register = [command.phrase] + list(command.aliases)
        for phrase in phrases_to_register:
            self.trie.insert(phrase, command)
            acoustic_phrase = config._to_acoustic_phrase(phrase)
            if acoustic_phrase and acoustic_phrase != phrase:
                self.trie.insert(acoustic_phrase, command)

    def get_command(self, command_id: str) -> Optional[CommandDefinition]:
        """Retrieve command by its unique identifier."""
        return self._commands.get(command_id)

    def evaluate(self, phrase: str) -> Tuple[MatchResult, Optional[CommandDefinition]]:
        """
        Evaluate recognized text against the command registry.
        Supports both deterministic Trie commands and dynamic search queries.
        Returns:
            (MatchResult, CommandDefinition or None)
        """
        trie_result, trie_cmd = self.trie.match(phrase)
        if trie_result == MatchResult.EXACT_MATCH:
            return trie_result, trie_cmd

        # Check for dynamic search queries
        cleaned = " ".join(phrase.strip().lower().split())
        if cleaned in (
            "search",
            "search for",
            "search on",
            "search on google",
            "search on youtube",
            "search on google for",
            "search on youtube for",
            "search in a new window",
            "search on google in a new window",
            "search on youtube in a new window",
        ):
            return MatchResult.PREFIX_ONLY, None

        if cleaned.startswith("search "):
            search_res = parse_search_query(phrase)
            if search_res is not None:
                search_cmd = create_search_command(search_res, phrase=phrase)
                return MatchResult.EXACT_MATCH, search_cmd

        return trie_result, trie_cmd

    def get_all_commands(self) -> List[CommandDefinition]:
        """Return list of all registered commands."""
        return list(self._commands.values())
