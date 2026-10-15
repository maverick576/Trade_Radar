"""Entrypoint script to run independent SQL verification."""

import asyncio

from traderadar.scripts.verify_stats import main

if __name__ == "__main__":
    asyncio.run(main())
