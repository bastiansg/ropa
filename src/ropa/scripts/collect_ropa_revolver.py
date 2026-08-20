import asyncio

from ropa.collectors import RopaRevolverCollector
from ropa.scripts.collect_data import collect_provider


def main() -> None:
    asyncio.run(
        collect_provider("Ropa Revolver", RopaRevolverCollector())
    )


if __name__ == "__main__":
    main()
