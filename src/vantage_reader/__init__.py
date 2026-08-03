"""Serial reader for the Davis Vantage Pro 2 console: wakes the console,
streams LOOP/LOOP2 packets, and produces Weather Report documents."""

from .console import ConsoleError, VantageConsole

__all__ = ["ConsoleError", "VantageConsole"]
