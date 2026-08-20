import asyncio

from ropa.collectors import AyNotDeadCollector
from ropa.scripts.collect_data import collect_provider


def main() -> None:
    asyncio.run(collect_provider("Ay Not Dead", AyNotDeadCollector()))


if __name__ == "__main__":
    main()
