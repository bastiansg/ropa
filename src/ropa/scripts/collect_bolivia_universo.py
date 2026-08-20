import asyncio

from ropa.collectors import BoliviaUniversoCollector
from ropa.scripts.collect_data import collect_provider


def main() -> None:
    asyncio.run(
        collect_provider("Bolivia - Divina", BoliviaUniversoCollector())
    )


if __name__ == "__main__":
    main()
