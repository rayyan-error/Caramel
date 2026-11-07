"""
Command Registry for Project Caramel / Uranus.
Maintains all active command definitions and builds the prefix tree.
"""

from typing import Dict, List, Optional, Tuple

from config.settings import CommandDefinition, config
from caramel.engine.trie import CommandTrie, MatchResult


class CommandRegistry:
    """
    Central registry that holds registered commands and compiles
    them into a deterministic prefix tree.
    """
    def __init__(self, commands: Optional[List[CommandDefinition]] = None):
        self._commands: Dict[str, CommandDefinition] = {}
        self.trie = CommandTrie()
        
        command_list = commands if commands is not None else config.COMMANDS
        for cmd in command_list:
            self.register(cmd)

    def register(self, command: CommandDefinition) -> None:
        """Register a command and its explicit phrase aliases into the Trie."""
        self._commands[command.command_id] = command
        # Insert primary phrase
        self.trie.insert(command.phrase, command)
        # Insert aliases (e.g. "open anti gravity")
        for alias in command.aliases:
            self.trie.insert(alias, command)

    def get_command(self, command_id: str) -> Optional[CommandDefinition]:
        """Retrieve command by its unique identifier."""
        return self._commands.get(command_id)

    def evaluate(self, phrase: str) -> Tuple[MatchResult, Optional[CommandDefinition]]:
        """
        Evaluate recognized text against the command registry.
        Returns:
            (MatchResult, CommandDefinition or None)
        """
        return self.trie.match(phrase)

    def get_all_commands(self) -> List[CommandDefinition]:
        """Return list of all registered commands."""
        return list(self._commands.values())
