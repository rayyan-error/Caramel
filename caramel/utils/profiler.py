"""
High-Precision Monotonic Latency Profiler and Resource Monitor.
Tracks end-to-end timing milestones and process resource utilization.
"""

from dataclasses import dataclass, field
import os
import time
from typing import Dict, List, Optional


@dataclass
class CommandMetrics:
    """Latency milestones for a single command execution cycle."""
    wake_detected_time: float = 0.0
    speech_start_time: float = 0.0
    eou_detected_time: float = 0.0
    match_completed_time: float = 0.0
    execution_completed_time: float = 0.0

    @property
    def speech_duration_ms(self) -> float:
        if self.speech_start_time > 0 and self.eou_detected_time > self.speech_start_time:
            return (self.eou_detected_time - self.speech_start_time) * 1000.0
        return 0.0

    @property
    def trie_lookup_ms(self) -> float:
        if self.match_completed_time > self.eou_detected_time:
            return (self.match_completed_time - self.eou_detected_time) * 1000.0
        return 0.0

    @property
    def spawn_latency_ms(self) -> float:
        if self.execution_completed_time > self.match_completed_time:
            return (self.execution_completed_time - self.match_completed_time) * 1000.0
        return 0.0

    @property
    def post_speech_turnaround_ms(self) -> float:
        """Total turnaround time from the moment speech ceased until execution dispatch."""
        if self.execution_completed_time > self.eou_detected_time:
            return (self.execution_completed_time - self.eou_detected_time) * 1000.0
        return 0.0


class PerformanceMonitor:
    """Monitors CPU and RAM footprint without third-party dependencies."""
    @staticmethod
    def get_memory_rss_mb() -> float:
        """Returns resident set size (RSS) in megabytes using /proc/self/statm."""
        try:
            with open("/proc/self/statm", "r") as f:
                parts = f.read().split()
                rss_pages = int(parts[1])
                page_size_kb = os.sysconf("SC_PAGE_SIZE") / 1024.0
                return (rss_pages * page_size_kb) / 1024.0
        except Exception:
            return 0.0

    @staticmethod
    def get_cpu_times() -> tuple[float, float]:
        """Returns (user_time_s, system_time_s) from /proc/self/stat."""
        try:
            with open("/proc/self/stat", "r") as f:
                parts = f.read().split()
                utime = float(parts[13]) / os.sysconf("SC_CLK_TCK")
                stime = float(parts[14]) / os.sysconf("SC_CLK_TCK")
                return utime, stime
        except Exception:
            return 0.0, 0.0
