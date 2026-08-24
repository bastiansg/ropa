from collections.abc import Iterable

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console(stderr=True)


def cyberpunk_table(title: str) -> Table:
    return Table(
        title=title,
        title_style="bold bright_magenta",
        border_style="dim magenta",
        header_style="bold bright_cyan",
        box=box.ASCII,
    )


def render_values(values: Iterable[object]) -> Text:
    return Text(" // ", style="bold bright_white").join(
        Text(str(value), style="dim white") for value in values
    )


def render_step(label: str, action: str) -> None:
    message = Text()
    message.append("\n┌─[ ", style="dim magenta")
    message.append(label, style="bold white")
    message.append(" ]\n", style="dim magenta")
    message.append("└──> ", style="dim magenta")
    message.append(action, style="dim bright_cyan")
    console.print(message)
