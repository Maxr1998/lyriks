from rich.console import Console
from rich.theme import Theme

custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
    }
)
console = Console(log_path=False, theme=custom_theme)
