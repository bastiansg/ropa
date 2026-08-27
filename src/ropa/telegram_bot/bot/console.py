from itertools import cycle

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

ROPA_BANNER = (
    "██████╗  ██████╗ ██████╗  █████╗ ",
    "██╔══██╗██╔═══██╗██╔══██╗██╔══██╗",
    "██████╔╝██║   ██║██████╔╝███████║",
    "██╔══██╗██║   ██║██╔═══╝ ██╔══██║",
    "██║  ██║╚██████╔╝██║     ██║  ██║",
    "╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝",
)

ROPA_STYLES = (
    "bold bright_magenta",
    "bold magenta",
    "bold bright_cyan",
)


def render_header() -> None:
    banner = Text()
    banner.append("\n\n")

    for line, style in zip(
        ROPA_BANNER,
        cycle(ROPA_STYLES),
        strict=False,
    ):
        banner.append(f"{line}\n", style=style)

    banner.append(
        "R.O.P.A ASSISTANT".center(len(ROPA_BANNER[0])),
        style="dim bright_magenta",
    )

    console.print(Align.center(banner))


def render_listening_status() -> None:
    console.print(
        Panel(
            "TELEGRAM POLLING // WAITING FOR INPUT",
            title="[bold]::: ROPA ASSISTANT IS LISTENING :::[/bold]",
            title_align="left",
            border_style="bright_cyan",
            box=box.ASCII,
            padding=(1, 2),
        )
    )
