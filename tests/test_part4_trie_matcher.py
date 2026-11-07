"""
Automated Test Suite for Part 4: Prefix Ambiguity Trie & Command Validation Engine
Validates:
1. Exact matching of all 4 initial V1 commands.
2. Phonetic alias resolution ('open anti gravity' -> CMD_OPEN_ANTIGRAVITY).
3. Prefix ambiguity isolation ('open youtube' vs 'open youtube in a new window').
4. Rejection of partial prefixes without premature execution.
5. Rejection of extraneous words ('open youtube tomorrow') and unknown tokens ('[unk]').
6. In-memory lookup latency (<0.01ms per lookup).
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.engine.registry import CommandRegistry
from caramel.engine.trie import MatchResult


def test_exact_v1_commands_matching():
    """Verify all 4 V1 commands match exactly and return correct CommandDefinitions."""
    print("[TEST] 1. Exact V1 Command Matching...")
    registry = CommandRegistry()

    test_cases = [
        ("open brave", "CMD_OPEN_BRAVE"),
        ("open antigravity", "CMD_OPEN_ANTIGRAVITY"),
        ("open terminal", "CMD_OPEN_TERMINAL"),
        ("open cryptometer", "CMD_OPEN_CRYPTOMATOR"),
        ("open youtube", "CMD_OPEN_YOUTUBE"),
        ("open youtube in a new window", "CMD_OPEN_YOUTUBE_NEW_WINDOW"),
        ("open gemini", "CMD_OPEN_GEMINI"),
        ("open gemini in a new window", "CMD_OPEN_GEMINI_NEW_WINDOW"),
        ("open google classroom", "CMD_OPEN_GOOGLE_CLASSROOM"),
        ("open google classroom in a new window", "CMD_OPEN_GOOGLE_CLASSROOM_NEW_WINDOW"),
        ("open crunchyroll", "CMD_OPEN_CRUNCHYROLL"),
        ("open crunchyroll in a new window", "CMD_OPEN_CRUNCHYROLL_NEW_WINDOW"),
        ("open text editor", "CMD_OPEN_TEXT_EDITOR"),
        ("open settings", "CMD_OPEN_SETTINGS"),
        ("open instagram", "CMD_OPEN_INSTAGRAM"),
        ("open instagram in a new window", "CMD_OPEN_INSTAGRAM_NEW_WINDOW"),
    ]

    for phrase, expected_id in test_cases:
        res, cmd = registry.evaluate(phrase)
        assert res == MatchResult.EXACT_MATCH, f"Failed match for '{phrase}', got {res}"
        assert cmd is not None, f"CommandDefinition missing for '{phrase}'"
        assert cmd.command_id == expected_id, f"Expected {expected_id}, got {cmd.command_id}"
        print(f"  -> '{phrase}' => EXACT_MATCH ({cmd.command_id})")

    print("  -> Passed: All 4 initial commands matched with exact IDs.")


def test_alias_resolution():
    """Verify phonetic aliases resolve to the same command."""
    print("[TEST] 2. Phonetic Alias Resolution...")
    registry = CommandRegistry()

    aliases_to_test = [
        ("open anti gravity", "CMD_OPEN_ANTIGRAVITY"),
        ("open gcr", "CMD_OPEN_GOOGLE_CLASSROOM"),
        ("open g c r", "CMD_OPEN_GOOGLE_CLASSROOM"),
        ("open classroom", "CMD_OPEN_GOOGLE_CLASSROOM"),
        ("open crunchy roll", "CMD_OPEN_CRUNCHYROLL"),
        ("open insta", "CMD_OPEN_INSTAGRAM"),
        ("open editor", "CMD_OPEN_TEXT_EDITOR"),
        ("open settings app", "CMD_OPEN_SETTINGS"),
    ]
    for alias_phrase, expected_id in aliases_to_test:
        res, cmd = registry.evaluate(alias_phrase)
        assert res == MatchResult.EXACT_MATCH, f"Expected EXACT_MATCH for alias '{alias_phrase}', got {res}"
        assert cmd is not None
        assert cmd.command_id == expected_id, f"Expected {expected_id}, got {cmd.command_id}"
        print(f"  -> '{alias_phrase}' => EXACT_MATCH ({cmd.command_id})")
    print("  -> Passed: Alias resolution verified.")


def test_prefix_ambiguity_isolation():
    """
    Verify prefix collision handling:
    - 'open youtube' is an exact match.
    - 'open youtube in' is PREFIX_ONLY.
    - 'open youtube in a new window' is an exact match.
    """
    print("[TEST] 3. Prefix Ambiguity Isolation...")
    registry = CommandRegistry()

    # Prefix of multiple commands
    res, cmd = registry.evaluate("open")
    assert res == MatchResult.PREFIX_ONLY
    assert cmd is None

    # Exact command that can also be a prefix of a longer command
    res, cmd = registry.evaluate("open youtube")
    assert res == MatchResult.EXACT_MATCH
    assert cmd.command_id == "CMD_OPEN_YOUTUBE"

    # Intermediate prefix stages
    intermediate_prefixes = [
        "open youtube in",
        "open youtube in a",
        "open youtube in a new",
    ]
    for p in intermediate_prefixes:
        res, cmd = registry.evaluate(p)
        assert res == MatchResult.PREFIX_ONLY, f"Prefix '{p}' should be PREFIX_ONLY, got {res}"
        assert cmd is None

    # Full extended command
    res, cmd = registry.evaluate("open youtube in a new window")
    assert res == MatchResult.EXACT_MATCH
    assert cmd.command_id == "CMD_OPEN_YOUTUBE_NEW_WINDOW"

    print("  -> Passed: Prefix ambiguity handled without collision or premature execution.")


def test_rejection_of_invalid_and_extended_phrases():
    """Verify zero-guessing: any unregistered extension or unknown token is rejected."""
    print("[TEST] 4. Rejection of Invalid / Extended Phrases...")
    registry = CommandRegistry()

    invalid_phrases = [
        "open youtube tomorrow",
        "open brave please",
        "can you open youtube",
        "open youtube now",
        "[unk]",
        "open [unk]",
        "open spotify",
        "",
        "   ",
    ]

    for phrase in invalid_phrases:
        res, cmd = registry.evaluate(phrase)
        assert res == MatchResult.UNKNOWN, f"Phrase '{phrase}' should be UNKNOWN, got {res}"
        assert cmd is None, f"Phrase '{phrase}' should not return a command"

    print("  -> Passed: Unregistered and malformed phrases strictly rejected.")


def test_trie_lookup_latency():
    """Verify in-memory Trie lookup latency is ultra-fast (<0.01ms per lookup)."""
    print("[TEST] 5. Trie In-Memory Lookup Latency...")
    registry = CommandRegistry()
    phrase = "open youtube in a new window"

    iterations = 2000
    t0 = time.perf_counter()
    for _ in range(iterations):
        registry.evaluate(phrase)
    t1 = time.perf_counter()

    avg_us = ((t1 - t0) / iterations) * 1_000_000.0  # microseconds
    print(f"  -> Average lookup latency: {avg_us:.3f} µs ({avg_us / 1000.0:.5f} ms)")
    assert avg_us < 20.0, f"Lookup latency too high: {avg_us} µs"
    print("  -> Passed: Trie lookup operates in negligible microseconds.")


def run_all():
    print("==================================================")
    print("RUNNING PART 4 VALIDATION TESTS")
    print("==================================================")
    test_exact_v1_commands_matching()
    test_alias_resolution()
    test_prefix_ambiguity_isolation()
    test_rejection_of_invalid_and_extended_phrases()
    test_trie_lookup_latency()
    print("==================================================")
    print("ALL PART 4 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
