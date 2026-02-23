"""
Script to create an EventLoop for arq's workers
This script solves discrepancies between arq's commands and python3.14.2
"""


import asyncio
from arq.worker import run_worker
from apps.bot.worker import WorkerSettings

if __name__ == '__main__':
    # Creating the event loop
    loop = asyncio.new_event_loop()
    # Telling python that this is the main Event Loop
    asyncio.set_event_loop(loop)

    run_worker(WorkerSettings)