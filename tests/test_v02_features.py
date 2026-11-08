"""
Comprehensive Test Suite for Project Caramel (Uranus v0.2) Features.
Validates:
1. Dynamic Google and YouTube search query parsing, URL encoding, and CommandDefinition synthesis.
2. Christ University CUE (portal / espro / attendance) and KnowledgePro (KP) navigation.
3. Expanded Web Hubs (Claude, WhatsApp Web, Spotify, Gmail, Reddit, Wikipedia).
4. LibreOffice Suite (Start Center, Writer, Calc, Impress, Draw) and desktop tools (Files, Calculator, System Monitor, ChatGPT).
5. Multimedia applications (VLC, GIMP, Krita, OBS Studio).
6. PipeWire volume controls (SYSTEM_ACTION via wpctl).
7. End-to-end State Machine dynamic search and command dispatch.
"""

import ctypes
import os
from pathlib import Path
import sys
import time
import urllib.parse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from caramel.audio.vad import SileroVAD
from caramel.engine.registry import CommandRegistry
from caramel.engine.search import SearchResult, create_search_command, parse_search_query
from caramel.engine.state_machine import AgentState, CaramelStateMachine
from caramel.engine.trie import MatchResult
from caramel.executor.launcher import ApplicationLauncher
from caramel.recognizer.vosk_engine import VoskRecognizerEngine
from config.settings import CommandDefinition, config


def test_dynamic_search_parsing_and_url_encoding():
    """Verify dynamic Google and YouTube search query extraction and URL generation."""
    print("[TEST] 1. Dynamic Search Parsing and URL Formatting...")

    # 1. Default Google Search
    res = parse_search_query("search how are rockets made")
    assert res is not None
    assert res.engine == "google"
    assert res.query == "how are rockets made"
    assert not res.new_window
    assert res.url == "https://www.google.com/search?q=how+are+rockets+made"

    # 2. Explicit Google Search with new window
    res = parse_search_query("search how are rockets made on google in a new window")
    assert res is not None
    assert res.engine == "google"
    assert res.query == "how are rockets made"
    assert res.new_window
    assert res.url == "https://www.google.com/search?q=how+are+rockets+made"

    # 3. YouTube Search
    res = parse_search_query("search how are rockets made on youtube")
    assert res is not None
    assert res.engine == "youtube"
    assert res.query == "how are rockets made"
    assert not res.new_window
    assert res.url == "https://www.youtube.com/results?search_query=how+are+rockets+made"

    # 4. YouTube Search in new window
    res = parse_search_query("search machine learning roadmap on youtube in a new window")
    assert res is not None
    assert res.engine == "youtube"
    assert res.query == "machine learning roadmap"
    assert res.new_window
    assert res.url == "https://www.youtube.com/results?search_query=machine+learning+roadmap"

    # 5. Queries with special symbols and URL quoting
    res = parse_search_query("search C++ & Python 3.12 on google")
    assert res is not None
    assert res.engine == "google"
    assert res.url == "https://www.google.com/search?q=c%2B%2B+%26+python+3.12"

    # 6. Preposition variations ("search on google for ...", "search for ... on youtube")
    res_prep1 = parse_search_query("search on google for christ university bangalore")
    assert res_prep1 is not None
    assert res_prep1.engine == "google"
    assert res_prep1.query == "christ university bangalore"

    res_prep2 = parse_search_query("search for interstellar soundtrack on youtube")
    assert res_prep2 is not None
    assert res_prep2.engine == "youtube"
    assert res_prep2.query == "interstellar soundtrack"

    # 7. Dynamic CommandDefinition construction & Launcher argv test
    launcher = ApplicationLauncher(dry_run=True)
    cmd = create_search_command(res, phrase="search how are rockets made on google")
    assert cmd.command_id == "CMD_SEARCH_GOOGLE"
    assert cmd.action_type == "OPEN_URL"
    assert cmd.target_app == "brave"

    valid, argv, err = launcher.build_command_args(cmd)
    assert valid, f"Failed building argv: {err}"
    assert argv[0] == config.get_app("brave").executable_path
    assert argv[-1] == res.url
    assert "--new-window" not in argv

    cmd_win = create_search_command(
        SearchResult("youtube", "space exploration", True, "https://www.youtube.com/results?search_query=space+exploration")
    )
    valid_win, argv_win, _ = launcher.build_command_args(cmd_win)
    assert valid_win
    assert "--new-window" in argv_win
    assert argv_win[-1] == "https://www.youtube.com/results?search_query=space+exploration"

    print("  -> Passed: Google and YouTube search query parsing and URL generation verified.")


def test_christ_university_portals():
    """Verify Christ University CUE and KnowledgePro portals with all aliases."""
    print("[TEST] 2. Christ University Portals (CUE & KnowledgePro)...")
    registry = CommandRegistry()
    launcher = ApplicationLauncher(dry_run=True)

    # 1. CUE / Espro / Attendance Portal (https://cue.christuniversity.in/main/home)
    cue_phrases = [
        "open christ university portal",
        "open portal",
        "open cue",
        "open espro",
        "open attendance",
    ]
    for p in cue_phrases:
        match_res, cmd = registry.evaluate(p)
        assert match_res == MatchResult.EXACT_MATCH, f"Failed match for '{p}'"
        assert cmd.command_id == "CMD_OPEN_CHRIST_PORTAL"
        assert cmd.url == "https://cue.christuniversity.in/main/home"
        assert not cmd.new_window

    # CUE new window variants
    cue_win_phrases = [
        "open christ university portal in a new window",
        "open portal in a new window",
        "open cue in a new window",
        "open espro in a new window",
        "open attendance in a new window",
    ]
    for p in cue_win_phrases:
        match_res, cmd = registry.evaluate(p)
        assert match_res == MatchResult.EXACT_MATCH, f"Failed match for '{p}'"
        assert cmd.command_id == "CMD_OPEN_CHRIST_PORTAL_NEW_WINDOW"
        assert cmd.url == "https://cue.christuniversity.in/main/home"
        assert cmd.new_window

    # 2. KnowledgePro Portal (https://kp.christuniversity.in/KnowledgePro/Login.do)
    kp_phrases = ["open kp", "open k p", "open knowledge pro"]
    for p in kp_phrases:
        match_res, cmd = registry.evaluate(p)
        assert match_res == MatchResult.EXACT_MATCH, f"Failed match for '{p}'"
        assert cmd.command_id == "CMD_OPEN_CHRIST_KP"
        assert cmd.url == "https://kp.christuniversity.in/KnowledgePro/Login.do"
        assert not cmd.new_window

    kp_win_phrases = [
        "open kp in a new window",
        "open k p in a new window",
        "open knowledge pro in a new window",
    ]
    for p in kp_win_phrases:
        match_res, cmd = registry.evaluate(p)
        assert match_res == MatchResult.EXACT_MATCH, f"Failed match for '{p}'"
        assert cmd.command_id == "CMD_OPEN_CHRIST_KP_NEW_WINDOW"
        assert cmd.url == "https://kp.christuniversity.in/KnowledgePro/Login.do"
        assert cmd.new_window

    print("  -> Passed: Christ University CUE and KnowledgePro navigation verified.")


def test_expanded_web_hubs():
    """Verify new web hubs: Claude, WhatsApp Web, Spotify, Gmail, Reddit, Wikipedia."""
    print("[TEST] 3. Expanded Web Hubs...")
    registry = CommandRegistry()

    hubs = [
        ("open claude", "CMD_OPEN_CLAUDE", "https://claude.ai", False),
        ("open claude in a new window", "CMD_OPEN_CLAUDE_NEW_WINDOW", "https://claude.ai", True),
        ("open whatsapp", "CMD_OPEN_WHATSAPP", "https://web.whatsapp.com", False),
        ("open whats app", "CMD_OPEN_WHATSAPP", "https://web.whatsapp.com", False),
        ("open whatsapp in a new window", "CMD_OPEN_WHATSAPP_NEW_WINDOW", "https://web.whatsapp.com", True),
        ("open spotify", "CMD_OPEN_SPOTIFY", "https://open.spotify.com", False),
        ("open spotify in a new window", "CMD_OPEN_SPOTIFY_NEW_WINDOW", "https://open.spotify.com", True),
        ("open gmail", "CMD_OPEN_GMAIL", "https://mail.google.com", False),
        ("open mail", "CMD_OPEN_GMAIL", "https://mail.google.com", False),
        ("open gmail in a new window", "CMD_OPEN_GMAIL_NEW_WINDOW", "https://mail.google.com", True),
        ("open reddit", "CMD_OPEN_REDDIT", "https://reddit.com", False),
        ("open reddit in a new window", "CMD_OPEN_REDDIT_NEW_WINDOW", "https://reddit.com", True),
        ("open wikipedia", "CMD_OPEN_WIKIPEDIA", "https://en.wikipedia.org", False),
        ("open wiki", "CMD_OPEN_WIKIPEDIA", "https://en.wikipedia.org", False),
        ("open wikipedia in a new window", "CMD_OPEN_WIKIPEDIA_NEW_WINDOW", "https://en.wikipedia.org", True),
    ]

    for phrase, expected_id, expected_url, expected_new_win in hubs:
        res, cmd = registry.evaluate(phrase)
        assert res == MatchResult.EXACT_MATCH, f"Failed match for '{phrase}'"
        assert cmd.command_id == expected_id, f"Expected {expected_id}, got {cmd.command_id}"
        assert cmd.url == expected_url, f"Expected {expected_url}, got {cmd.url}"
        assert cmd.new_window == expected_new_win

    print("  -> Passed: Web hubs matched with exact URLs and window modes.")


def test_libreoffice_and_desktop_applications():
    """Verify LibreOffice suite, Nautilus Files, Calculator, System Monitor, and ChatGPT."""
    print("[TEST] 4. LibreOffice Suite and Desktop Applications...")
    registry = CommandRegistry()
    launcher = ApplicationLauncher(dry_run=True)

    test_apps = [
        ("open libreoffice", "CMD_OPEN_LIBREOFFICE", "libreoffice", []),
        ("open writer", "CMD_OPEN_WRITER", "libreoffice_writer", ["--writer"]),
        ("open document", "CMD_OPEN_WRITER", "libreoffice_writer", ["--writer"]),
        ("open calc", "CMD_OPEN_CALC", "libreoffice_calc", ["--calc"]),
        ("open spreadsheet", "CMD_OPEN_CALC", "libreoffice_calc", ["--calc"]),
        ("open impress", "CMD_OPEN_IMPRESS", "libreoffice_impress", ["--impress"]),
        ("open presentation", "CMD_OPEN_IMPRESS", "libreoffice_impress", ["--impress"]),
        ("open draw", "CMD_OPEN_DRAW", "libreoffice_draw", ["--draw"]),
        ("open files", "CMD_OPEN_FILES", "files", []),
        ("open file manager", "CMD_OPEN_FILES", "files", []),
        ("open calculator", "CMD_OPEN_CALCULATOR", "calculator", []),
        ("open system monitor", "CMD_OPEN_SYSTEM_MONITOR", "system_monitor", []),
        ("open chatgpt app", "CMD_OPEN_CHATGPT", "chatgpt", []),
        ("open vlc", "CMD_OPEN_VLC", "vlc", []),
        ("open gimp", "CMD_OPEN_GIMP", "gimp", []),
        ("open krita", "CMD_OPEN_KRITA", "krita", []),
        ("open obs", "CMD_OPEN_OBS", "obs", []),
    ]

    for phrase, expected_id, expected_target, expected_flags in test_apps:
        res, cmd = registry.evaluate(phrase)
        assert res == MatchResult.EXACT_MATCH, f"Failed match for '{phrase}'"
        assert cmd.command_id == expected_id, f"Expected {expected_id}, got {cmd.command_id}"
        assert cmd.target_app == expected_target

        valid, argv, err = launcher.build_command_args(cmd)
        assert valid, f"Failed building argv for {cmd.command_id}: {err}"
        for flag in expected_flags:
            assert flag in argv, f"Flag {flag} missing in {argv}"

    print("  -> Passed: LibreOffice suite and desktop tools compiled with exact flags.")


def test_system_volume_controls():
    """Verify SYSTEM_ACTION commands for PipeWire volume control (wpctl)."""
    print("[TEST] 5. System Audio Volume Controls (wpctl)...")
    registry = CommandRegistry()
    launcher = ApplicationLauncher(dry_run=True)

    vol_tests = [
        ("volume up", "CMD_VOLUME_UP", ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"]),
        ("increase volume", "CMD_VOLUME_UP", ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"]),
        ("volume down", "CMD_VOLUME_DOWN", ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"]),
        ("decrease volume", "CMD_VOLUME_DOWN", ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"]),
        ("mute volume", "CMD_MUTE_VOLUME", ["set-mute", "@DEFAULT_AUDIO_SINK@", "1"]),
        ("mute audio", "CMD_MUTE_VOLUME", ["set-mute", "@DEFAULT_AUDIO_SINK@", "1"]),
        ("unmute volume", "CMD_UNMUTE_VOLUME", ["set-mute", "@DEFAULT_AUDIO_SINK@", "0"]),
        ("unmute audio", "CMD_UNMUTE_VOLUME", ["set-mute", "@DEFAULT_AUDIO_SINK@", "0"]),
    ]

    for phrase, expected_id, expected_tail in vol_tests:
        res, cmd = registry.evaluate(phrase)
        assert res == MatchResult.EXACT_MATCH, f"Failed match for '{phrase}'"
        assert cmd.command_id == expected_id
        assert cmd.action_type == "SYSTEM_ACTION"

        valid, argv, err = launcher.build_command_args(cmd)
        assert valid, f"Failed building argv for {expected_id}: {err}"
        assert argv[1:] == expected_tail

    print("  -> Passed: PipeWire volume control actions verified.")


def test_real_audio_e2e_search_and_v02_commands():
    """
    Verify complete unmocked end-to-end CaramelStateMachine pipeline with speech synthesis
    for dynamic search and v0.2 voice commands.
    """
    print("[TEST] 6. Real-Audio End-to-End Simulation (Vosk + StateMachine)...")
    espeak_lib_path = Path("/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1")
    if not espeak_lib_path.is_file():
        print("  -> Skipped (libespeak-ng not installed)")
        return

    lib = ctypes.CDLL(str(espeak_lib_path))
    samples_list = []
    SYNTH_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

    def _cb(wav, numsamples, events):
        if wav and numsamples > 0:
            samples_list.append(np.ctypeslib.as_array(wav, shape=(numsamples,)).copy())
        return 0

    c_cb = SYNTH_CB(_cb)
    sr = lib.espeak_Initialize(2, 0, None, 0)
    lib.espeak_SetSynthCallback(c_cb)
    lib.espeak_SetVoiceByName(b"en-us")

    def synth_16k(text_str: str) -> np.ndarray:
        samples_list.clear()
        b = text_str.encode("utf-8")
        lib.espeak_Synth(b, len(b) + 1, 0, 0, 0, 0, None, None)
        pcm = np.concatenate(samples_list)
        target_len = int(len(pcm) * 16000 / sr)
        return np.interp(
            np.linspace(0, len(pcm) - 1, target_len),
            np.arange(len(pcm)),
            pcm
        ).astype(np.int16)

    sm = CaramelStateMachine(dry_run=True)

    scenarios = [
        # 1. Dynamic Google Search
        (
            "Caramel, search how rockets are made on Google",
            "caramel search how rockets are made on google",
            "CMD_SEARCH_GOOGLE",
            "https://www.google.com/search?q=how+rockets+are+made"
        ),
        # 2. Dynamic YouTube Search
        (
            "Caramel, search how rockets are made on YouTube",
            "caramel search how rockets are made on youtube",
            "CMD_SEARCH_YOUTUBE",
            "https://www.youtube.com/results?search_query=how+rockets+are+made"
        ),
        # 3. Christ University Attendance
        (
            "Caramel, open attendance",
            "caramel open attendance",
            "CMD_OPEN_CHRIST_PORTAL",
            "https://cue.christuniversity.in/main/home"
        ),
        # 4. Christ University KnowledgePro
        (
            "Caramel, open KP",
            "caramel open k p",
            "CMD_OPEN_CHRIST_KP",
            "https://kp.christuniversity.in/KnowledgePro/Login.do"
        ),
        # 5. Volume Up
        (
            "Caramel, volume up",
            "caramel volume up",
            "CMD_VOLUME_UP",
            None
        ),
        # 6. LibreOffice Writer
        (
            "Caramel, open writer",
            "caramel open writer",
            "CMD_OPEN_WRITER",
            None
        ),
    ]

    for label, spoken_text, expected_cmd_id, expected_url in scenarios:
        audio = np.concatenate([
            np.zeros(3200, dtype=np.int16),
            synth_16k(spoken_text),
            np.zeros(12000, dtype=np.int16)
        ])

        executed_commands = []
        sm.on_command_executed = lambda res: executed_commands.append(res)
        sm.cancel()

        chunk_size = 512
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            sm.process_chunk(chunk)

        assert len(executed_commands) == 1, f"Failed execution for {label}: got {executed_commands}"
        res = executed_commands[0]
        assert res.command_id == expected_cmd_id, f"Expected {expected_cmd_id}, got {res.command_id}"
        if expected_url:
            assert res.executed_args[-1] == expected_url, f"Expected URL {expected_url}, got {res.executed_args[-1]}"
        print(f"  -> {label:<50} => {res.command_id} ({res.executed_args})")

    print("  -> Passed: Unmocked end-to-end audio pipeline verified for all v0.2 scenarios.")


def run_all():
    print("==================================================")
    print("RUNNING VERSION 0.2 FEATURE VALIDATION TESTS")
    print("==================================================")
    test_dynamic_search_parsing_and_url_encoding()
    test_christ_university_portals()
    test_expanded_web_hubs()
    test_libreoffice_and_desktop_applications()
    test_system_volume_controls()
    test_real_audio_e2e_search_and_v02_commands()
    print("==================================================")
    print("ALL VERSION 0.2 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
