from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

# Change if needed
MY_EMAIL = "yefetm123456@gmail.com"


def get_credentials() -> Credentials:
    creds: Optional[Credentials] = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        Path(TOKEN_FILE).write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_services(creds: Credentials):
    gmail_service = build("gmail", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    return gmail_service, calendar_service


def get_recent_email_ids(gmail_service, days: int = 2, max_results: int = 10) -> list[str]:
    query = f"newer_than:{days}d"

    result = (
        gmail_service.users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=max_results
        )
        .execute()
    )

    return [msg["id"] for msg in result.get("messages", [])]


def get_message_text(gmail_service, message_id: str) -> dict[str, str]:
    msg = (
        gmail_service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers = msg.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
    sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "")
    snippet = msg.get("snippet", "")

    body_text = extract_body_text(msg.get("payload", {}))

    return {
        "id": message_id,
        "subject": subject,
        "from": sender,
        "snippet": snippet,
        "body": body_text or snippet,
    }


def extract_body_text(payload: dict[str, Any]) -> str:
    """Extract plain text from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return decode_base64url(data)

    parts = payload.get("parts", [])
    for part in parts:
        text = extract_body_text(part)
        if text:
            return text

    return ""


def decode_base64url(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")


def detect_meeting_request(email: dict[str, str]) -> bool:
    text = f"{email['subject']} {email['body']}".lower()
    keywords = [
        "meeting",
        "calendar",
        "zoom",
        "teams",
        "appointment",
        "schedule",
        "פגישה",
        "זום",
        "תיאום",
        "להיפגש",
        "ישיבה",
        "דיון",
    ]
    return any(word in text for word in keywords)


def extract_meeting_details(email: dict[str, str]) -> dict[str, Any]:
    """
    Basic rule-based extraction.
    For higher grade: replace/extend with LLM extraction.
    """
    text = f"{email['subject']}\n{email['body']}"

    date_match = re.search(r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", text)
    time_match = re.search(r"(\d{1,2}:\d{2})", text)

    location = "Online / Not specified"
    for keyword in ["Zoom", "zoom", "Teams", "teams", "Google Meet", "חדר", "משרד", "קריה"]:
        if keyword in text:
            location = keyword
            break

    return {
        "title": email["subject"] or "Meeting from Gmail",
        "date": date_match.group(1) if date_match else None,
        "time": time_match.group(1) if time_match else None,
        "location": location,
        "participants": [email["from"], MY_EMAIL],
        "source_message_id": email["id"],
    }


def parse_datetime(date_str: str | None, time_str: str | None) -> Optional[datetime]:
    if not date_str or not time_str:
        return None

    for fmt in ["%d/%m/%Y %H:%M", "%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%y %H:%M", "%d.%m.%y %H:%M"]:
        try:
            return datetime.strptime(f"{date_str} {time_str}", fmt).astimezone()
        except ValueError:
            continue

    return None


def is_calendar_free(calendar_service, start_time: datetime, end_time: datetime) -> bool:
    body = {
        "timeMin": start_time.isoformat(),
        "timeMax": end_time.isoformat(),
        "items": [{"id": "primary"}],
    }

    result = calendar_service.freebusy().query(body=body).execute()
    busy_slots = result["calendars"]["primary"].get("busy", [])
    return len(busy_slots) == 0


def create_calendar_event(calendar_service, details: dict[str, Any], start_time: datetime, end_time: datetime):
    event = {
        "summary": details["title"],
        "location": details.get("location", ""),
        "description": "Created automatically by Gmail & Calendar AI Agent.",
        "start": {"dateTime": start_time.isoformat()},
        "end": {"dateTime": end_time.isoformat()},
        "attendees": [{"email": MY_EMAIL}],
    }

    created = calendar_service.events().insert(calendarId="primary", body=event).execute()
    return created["id"], created.get("htmlLink")


def create_unavailable_draft(gmail_service, original_email: dict[str, str], details: dict[str, Any]):
    msg = EmailMessage()
    msg["To"] = MY_EMAIL
    msg["Subject"] = f"Re: {original_email['subject']}"
    msg.set_content(
        "שלום,\n\n"
        "תודה על ההזמנה לפגישה.\n"
        "בדקנו את היומן שלנו ולצערנו איננו פנויים במועד שהוצע.\n"
        "נשמח לתאם מועד חלופי.\n\n"
        "בברכה,\n"
        "יפת משולם ואדיר נחמיאס\n"
    )

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = (
        gmail_service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return draft["id"]

def run_agent():
    creds = get_credentials()
    gmail_service, calendar_service = build_services(creds)

    email_ids = get_recent_email_ids(gmail_service, days=2, max_results=10)

    if not email_ids:
        print("No recent emails found.")
        return

    print(f"Found {len(email_ids)} recent emails.")

    for message_id in email_ids:
        email = get_message_text(gmail_service, message_id)
        print(f"\nChecking email: {email['subject']}")

        if not detect_meeting_request(email):
            print("Not a meeting request.")
            continue

        print("Meeting request detected.")
        details = extract_meeting_details(email)
        print(json.dumps(details, ensure_ascii=False, indent=2))

        start_time = parse_datetime(details.get("date"), details.get("time"))

        if start_time is None:
            print("Missing date/time. Skipping automatic calendar creation.")
            continue

        end_time = start_time + timedelta(hours=1)

        if is_calendar_free(calendar_service, start_time, end_time):
            event_id, event_link = create_calendar_event(calendar_service, details, start_time, end_time)
            print(f"Calendar event created: {event_id}")
            print(f"Event link: {event_link}")
        else:
            draft_id = create_unavailable_draft(gmail_service, email, details)
            print(f"Calendar is busy. Unavailable reply draft created: {draft_id}")


if __name__ == "__main__":
    run_agent()
