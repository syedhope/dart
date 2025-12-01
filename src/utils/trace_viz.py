# ==============================================================================
# File Location: dart-agent/src/utils/trace_viz.py
# File Name: trace_viz.py
# Description:
# - Rich-based trace logger for console/file output with incident-aware logging.
# - Provides table/panel helpers and stores history for UI mirroring.
# Inputs:
# - Log messages (source/level/text), incident IDs, and data tables.
# Outputs:
# - Console/file logs, rendered tables/panels, and stored history consumed by UI bridge.
# ==============================================================================

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from datetime import datetime
from typing import Dict, Any, List
import os
from src.utils.config import config 

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "bold magenta",
    "error": "bold red",
    "success": "bold green",
    "agent_syx": "bold blue",
    "agent_neon": "bold yellow",
    "agent_kai": "bold purple",
})

console = Console(theme=custom_theme)

class TraceLogger:
    def __init__(self):
        self.history = [] 
        
        # --- File Logging Setup ---
        self.log_dir = config.logs_dir
        if not os.path.exists(self.log_dir):
            try:
                os.makedirs(self.log_dir)
            except OSError:
                pass 

        session_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_filepath = os.path.join(self.log_dir, f"dart_session_{session_ts}.log")
        self._write_to_file(f"=== D.A.R.T. SESSION LOG STARTED: {session_ts} ===\n")

    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S")

    def _write_to_file(self, text: str):
        try:
            with open(self.log_filepath, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass 

    def header(self, title: str, subtitle: str = ""):
        console.print()
        console.print(Panel(Text(subtitle, justify="center"), title=f"[bold green]{title}", expand=False))
        self._write_to_file(f"\n{'-'*40}\n[{title}] {subtitle}\n{'-'*40}\n")

    def log(self, source: str, message: str, level: str = "info", incident_id: str = None):
        """
        General logger.
        Supports incident_id for session tracing.
        """
        time_str = self._timestamp()
        
        # Prepend ID for file/console logging if available
        id_prefix = f"[{incident_id[:8]}] " if incident_id else ""
        
        style = "white"
        if source == "Syx": style = "agent_syx"
        elif source == "Neon": style = "agent_neon"
        elif source == "Kai": style = "agent_kai"
        
        formatted_msg = f"[{level}][{time_str}] {id_prefix}{source}:[/] [{style}]{message}[/]"
        console.print(formatted_msg)
        
        try:
            plain_msg = Text.from_markup(message).plain
        except:
            plain_msg = message
            
        file_entry = f"[{time_str}] [{level.upper()}] {id_prefix}{source}: {plain_msg}\n"
        self._write_to_file(file_entry)
        
        self.history.append({"time": time_str, "source": source, "message": message, "level": level, "id": incident_id})

    def agent_thought(self, agent_name: str, thought: str, incident_id: str = None):
        id_prefix = f"[{incident_id[:8]}] " if incident_id else ""
        
        console.print(f"   [dim]💭 {id_prefix}{agent_name} is thinking: {thought}[/]")
        self._write_to_file(f"   (THOUGHT) {id_prefix}{agent_name}: {thought}\n")

    def show_table(self, title: str, data: List[Dict[str, Any]]):
        if not data:
            console.print(f"[warning]No data to display for {title}[/]")
            self._write_to_file(f"[{title}] No data.\n")
            return

        table = Table(title=title, show_header=True, header_style="bold magenta")
        headers = list(data[0].keys())
        for h in headers:
            table.add_column(h.capitalize())
        for item in data:
            row = [str(item.get(h, "")) for h in headers]
            table.add_row(*row)
        console.print(table)
        
        self._write_to_file(f"\n--- TABLE: {title} ---\n")
        for item in data:
            self._write_to_file(str(item) + "\n")
        self._write_to_file("----------------------\n")

# Global Singleton
trace = TraceLogger()
