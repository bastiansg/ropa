import json
from collections.abc import Iterable
from typing import Any

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


def render_node_detail(
    label: str,
    value: object,
) -> None:
    detail = Text()
    detail.append(" :: ", style="dim magenta")
    detail.append(
        label.replace("_", " ").upper(),
        style="bold white",
    )

    detail.append(" // ", style="dim magenta")
    detail.append(str(value), style="dim white")
    console.print(detail)


def render_tool_call(
    tool_name: str,
    parameters: dict[str, Any],
) -> None:
    label = tool_name.replace("_", " ").upper()
    formatted_parameters = json.dumps(
        parameters,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    message = Text()
    message.append("\n┌─[ ", style="dim magenta")
    message.append(f"TOOL // {label} ]\n", style="bold white")
    message.append("├── PARAMETERS\n", style="dim magenta")

    message.append(
        "\n".join(f"│   {line}" for line in formatted_parameters.splitlines()),
        style="dim white",
    )
    message.append("\n", style="dim white")
    message.append("└──> INVOKING TOOL...", style="dim bright_cyan")
    console.print(message)
