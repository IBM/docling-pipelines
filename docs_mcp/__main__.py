"""Entry point: python -m mcp_server"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    from docs_mcp.server import run

    asyncio.run(run())


if __name__ == "__main__":
    main()
