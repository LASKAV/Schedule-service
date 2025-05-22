import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from task_handler import process_all_tasks

scheduler = AsyncIOScheduler()


@scheduler.scheduled_job("interval", seconds=30)
async def scheduled_task():
    await process_all_tasks()


def main():
    scheduler.start()

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("Application is stopping...")


if __name__ == "__main__":
    main()
