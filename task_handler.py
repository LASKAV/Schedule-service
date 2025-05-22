import asyncio
import traceback
from datetime import datetime, timezone

from api_requests import (
    send_message_to_user,
    delete_sent,
    get_online_status_by_user,
    get_all_pending_tasks,
    by_pairs,
    send_mail_to_user,
)

from collections import defaultdict


# Mulynexus_backend (message_scheduler/get_scheduled_messages)
def group_tasks_by_user(tasks: list[dict]) -> dict[int, list[dict]]:
    grouped_tasks = defaultdict(list)
    for task in tasks:
        grouped_tasks[task["user_id"]].append(task)
    return grouped_tasks


async def handle_online_task(task: dict, online_status: dict):
    user_id = task["user_id"]
    task_id = task["id"]
    recipient_id = task["recipient_id"]
    talky_user_id = task["talky_user_id"]
    text = task["text"]
    resource_type = "message" if task["type_message"] else "mail"

    media = []
    if resource_type == "mail":
        media = task.get("media", [])
        photos = media["photos"]
        videos = media["videos"]
        payload = {
            "user_id": user_id,
            "idUserTo": recipient_id,
            "content": text,
            "images": photos,
            "videos": videos,
        }

    if online_status.get(str(recipient_id)):
        user_can_send = await by_pairs(
            user_id, talky_user_id, recipient_id, resource_type
        )
        if user_can_send:
            if resource_type == "message":
                await send_message_to_user(
                    user_id, talky_user_id, recipient_id, media, text, resource_type
                )
            elif resource_type == "mail":

                await send_mail_to_user(
                    user_id, talky_user_id, recipient_id, media, text, resource_type
                )
        await delete_sent(task_id, resource_type)


async def handle_timed_task(task: dict, now: datetime):
    user_id = task["user_id"]
    task_id = task["id"]
    recipient_id = task["recipient_id"]
    talky_user_id = task["talky_user_id"]
    text = task["text"]
    send_at = datetime.fromisoformat(task["send_at"])
    resource_type = "message" if task["type_message"] else "mail"

    media = []
    if resource_type == "mail":
        media = task.get("media", [])

    if send_at <= now.replace(tzinfo=None):
        user_can_send = await by_pairs(
            user_id, talky_user_id, recipient_id, resource_type
        )
        if user_can_send:
            if resource_type == "message":
                await send_message_to_user(
                    user_id, talky_user_id, recipient_id, media, text, resource_type
                )
            elif resource_type == "mail":
                await send_mail_to_user(
                    user_id, talky_user_id, recipient_id, media, text, resource_type
                )
        await delete_sent(task_id, resource_type)


async def process_tasks_for_user(user_id, tasks: list[dict]):
    now = datetime.now(tz=timezone.utc)

    valid_tasks = [task for task in tasks if isinstance(task, dict)]

    online_tasks = [task for task in valid_tasks if task.get("online_only")]
    if online_tasks:
        online_status = await get_online_status_by_user(user_id, online_tasks)

        for task in online_tasks:
            try:
                await handle_online_task(task, online_status)
            except Exception:
                traceback.print_exc()

    timed_tasks = [
        task
        for task in valid_tasks
        if task.get("send_at") and not task.get("online_only", False)
    ]

    for task in timed_tasks:
        try:
            await handle_timed_task(task, now)
        except Exception:
            traceback.print_exc()


# Fetch tasks for messages and mails
async def process_all_tasks():
    # Fetch tasks for messages and mails asynchronously
    tasks_messages = await get_all_pending_tasks("messages")
    tasks_mails = await get_all_pending_tasks("mails")

    # Combine all tasks (messages and mails) into a single list
    all_tasks = tasks_messages + tasks_mails

    # Group tasks by user
    tasks_by_user = group_tasks_by_user(all_tasks)

    # Process tasks for each user concurrently using asyncio.gather
    await asyncio.gather(
        *(
            process_tasks_for_user(user_id, user_tasks)
            for user_id, user_tasks in tasks_by_user.items()
        )
    )
