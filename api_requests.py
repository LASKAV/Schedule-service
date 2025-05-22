import logging
import os
import traceback
from datetime import datetime, timezone

import aiohttp
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


# SERVER @internal_bp.route("/online", methods=["POST"])
def chunk_list(lst: list, chunk_size: int) -> list[list]:
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


async def send_online_status_request(
    session: aiohttp.ClientSession, user_id: int, data: dict, url: str
) -> dict:
    payload = {"user_id": user_id, "data": data}
    try:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(
                    f"[{datetime.now()}] Unexpected response status: {response.status} for data: {data}"
                )
                return {}
    except aiohttp.ClientResponseError as e:
        traceback.print_exc()
        return {}


async def get_online_status_by_user(user_id: int, tasks: list[dict]) -> dict:
    url = f"{API_BASE_URL}/internal-scheduled/online"
    grouped_by_talky_user = {}

    for task in tasks:
        if not isinstance(task, dict):
            continue
        talky_user_id = task.get("talky_user_id")
        recipient_id = task.get("recipient_id")
        if talky_user_id is None or recipient_id is None:
            continue
        grouped_by_talky_user.setdefault(talky_user_id, []).append(recipient_id)

    if not grouped_by_talky_user:
        return {}

    requests_to_send = []
    for talky_user, recipients in grouped_by_talky_user.items():
        if len(recipients) > 49:
            for chunk in chunk_list(recipients, 49):
                requests_to_send.append({talky_user: chunk})
        else:
            requests_to_send.append({talky_user: recipients})

    result = {}
    async with aiohttp.ClientSession() as session:
        for data in requests_to_send:
            response_data = await send_online_status_request(
                session, user_id, data, url
            )
            if isinstance(response_data, dict):
                result.update(response_data)

    return result


# SERVER @internal_bp.route.route("/text", methods=["POST"])
async def send_message_to_user(
    user_id, girl_id: int, recipient_id: int, media, text, resource_type: str
) -> dict:
    # URL for sending text message

    url = f"{API_BASE_URL}/internal-scheduled/chat/send/text"

    match resource_type:
        case "message":
            payload = {
                "user_id": user_id,
                "idUser": girl_id,
                "idRegularUser": recipient_id,
                "message": text,
            }
        case _:
            raise ValueError("Invalid resource type. Use 'message' or 'mail'.")

    async with aiohttp.ClientSession() as session:
        # Sending POST request to the API with the message data
        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            resp = await response.json()
            await trigger_scheduled(
                girl_id=girl_id,
                recipient_id=recipient_id,
                message_data=resp,
                message_text=text,
                media=media,
                resource_type=resource_type,
            )
            return resp


# SERVER @internal_bp.route.route("/send-letter", methods=["POST"])
async def send_mail_to_user(
    user_id, girl_id: int, recipient_id: int, media, text, resource_type: str
) -> dict:
    # URL for sending text message
    url = f"{API_BASE_URL}/internal-scheduled/send-letter"
    photos = [{"idPhoto": photo["id"]} for photo in media["photos"]]
    videos = [{"idVideo": video["id"]} for video in media["videos"]]

    payload = {
        "user_id": user_id,
        "idUser": girl_id,
        "idUserTo": recipient_id,
        "content": text,
        "images": photos,
        "videos": videos,
    }

    async with aiohttp.ClientSession() as session:
        # Sending POST request to the API with the message data
        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            resp = await response.json()
            if response.status != 200:
                logger.error(
                    f"[{datetime.now()}]Unexpected response status: {response.status}, send mail , girl: {girl_id}, user: {user_id}"
                )

            return resp


# SERVER @internal_bp.route("/mail/<int:mail_id>",
# "/message/<int:message_id>" methods=["DELETE"])
async def delete_sent(task_id: int, resource_type: str) -> aiohttp.ClientResponse:
    match resource_type:
        case "message":
            url = f"{API_BASE_URL}/internal-scheduled/message/{task_id}"
        case "mail":
            url = f"{API_BASE_URL}/internal-scheduled/mail/{task_id}"
        case _:
            raise ValueError("Invalid resource type. Use 'message' or 'mail'.")

    # Send DELETE request to the selected URL
    async with aiohttp.ClientSession() as session:
        async with session.delete(url) as response:
            response.raise_for_status()
            return response


# @internal_bp.route("/mails", /messages methods=["GET"])
async def get_all_pending_tasks(resource_type: str) -> list[dict]:
    match resource_type:
        case "messages":
            url = f"{API_BASE_URL}/internal-scheduled/messages"
        case "mails":
            url = f"{API_BASE_URL}/internal-scheduled/mails"
        case _:
            raise ValueError("Invalid resource type. Use 'message' or 'mail'.")

    params = {"is_sent": False}
    params = {
        key: int(value) if isinstance(value, bool) else value
        for key, value in params.items()
    }

    all_tasks = []

    # Make API calls
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                tasks = await response.json()
                for task in tasks:
                    user_id = task.get("user_id")
                    if user_id:
                        task["user_id"] = user_id
                    all_tasks.append(task)
        except Exception as e:
            traceback.print_exc()
    return all_tasks


async def by_pairs(user_id, talky_user_id, recipient_id, resource_type):
    url = f"{API_BASE_URL}/internal-scheduled/dialogs/by-pairs"
    params = {
        "idsRegularUser": recipient_id,
        "idUser": talky_user_id,
        "user_id": user_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(
                    f"[{datetime.now()}]Unexpected response status: {response.status}, by pairs , girl: {talky_user_id}, user: {user_id}"
                )
            try:
                response_json = await response.json()
            except Exception as e:
                traceback.print_exc()
                return False

    for dialog in response_json.get("dialogs", []):
        if dialog.get("idUser") != talky_user_id:
            continue

        if dialog.get("isBlocked"):
            return False

        messages_left = dialog.get("messagesLeft") or 0
        if resource_type == "message" and messages_left == 0:
            return False

        if resource_type == "mail":
            data, status = await internal_restriction(
                user_id, talky_user_id, recipient_id
            )
            if status != 200 or (data.get("lettersLeft") or 0) == 0:
                return False

        return True

    return False


async def trigger_scheduled(
    girl_id, recipient_id, message_data, message_text, media, resource_type: str
):
    current_time = datetime.now(timezone.utc)
    date = current_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    # Extract the message ID from the message data
    message_id = message_data.get("idMessage")

    match resource_type:
        case "message":
            url = f"{API_BASE_URL}/internal-scheduled/trigger/message"
            payload = {
                "girl_id": girl_id,
                "id_interlocutor": recipient_id,
                "date": date,
                "message_text": message_text,
                "message_id": message_id,
            }
        case "mail":
            url = f"{API_BASE_URL}/internal-scheduled/trigger/mail"
            payload = {
                "girl_id": girl_id,
                "id_interlocutor": recipient_id,
                "date": date,
                "message_text": message_text,
                "message_id": message_id,
                "media": media,
            }
        case _:
            raise ValueError("Invalid resource type. Use 'message' or 'mail'.")

    # Send a POST request to trigger the scheduled message or mail
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            # Raise an exception if the response status is not 2xx (success)
            response.raise_for_status()


async def internal_restriction(user_id, talky_user_id, recipient_id):
    url = f"{API_BASE_URL}/internal-engage-tracker/chat/restriction"
    params = {
        "idRegularUser": recipient_id,
        "idUser": talky_user_id,
        "user_id": user_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(
                    f"[{datetime.now()}]Unexpected response status: {response.status}, restriction , girl: {talky_user_id}, user: {user_id}"
                )
            try:
                response_json = await response.json()
            except Exception as e:
                traceback.print_exc()
                return {}, response.status
            return response_json.get("data"), response.status
