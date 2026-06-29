from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
MY_EMAIL = "yefetm123456@gmail.com"


# ─────────────────────────────────────────────
#  Google Auth
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
#  Gmail helpers
# ─────────────────────────────────────────────
def get_recent_email_ids(gmail_service, days: int = 2, max_results: int = 10) -> list[str]:
    result = (
        gmail_service.users()
        .messages()
        .list(userId="me", q=f"newer_than:{days}d", maxResults=max_results)
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
    body_text = _extract_body_text(msg.get("payload", {}))

    return {
        "id": message_id,
        "subject": subject,
        "from": sender,
        "snippet": snippet,
        "body": body_text or snippet,
    }


def _extract_body_text(payload: dict[str, Any]) -> str:
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        text = _extract_body_text(part)
        if text:
            return text
    return ""


# ─────────────────────────────────────────────
#  Step 1: Detect meeting request (keywords)
# ─────────────────────────────────────────────
def detect_meeting_request(email: dict[str, str]) -> bool:
    text = f"{email['subject']} {email['body']}".lower()
    keywords = [
        "meeting", "calendar", "zoom", "teams", "appointment",
        "schedule", "call", "invite", "conference",
        "פגישה", "זום", "תיאום", "להיפגש", "ישיבה", "דיון", "הזמנה",
        "נפגש", "להיפגש", "קפה", "שיחה", "ראיון",
    ]
    matched = [kw for kw in keywords if kw in text]
    if matched:
        print(f"[detect] matched keywords: {matched}")
        return True
    return False


# ─────────────────────────────────────────────
#  Step 2: Extract meeting details (regex)
# ─────────────────────────────────────────────
def extract_meeting_details(email: dict[str, str]) -> dict[str, Any]:
    text = f"{email['subject']}\n{email['body']}"

    date_match = re.search(r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", text)
    time_match = re.search(r"(\d{1,2}:\d{2})", text)

    location = "Not specified"
    for kw in ["Zoom", "Teams", "Google Meet", "Meet", "zoom", "teams",
               "חדר", "משרד", "קריה", "אונליין", "online"]:
        if kw in text:
            location = kw
            break

    details = {
        "title": email["subject"] or "Meeting from Gmail",
        "date": date_match.group(1) if date_match else None,
        "time": time_match.group(1) if time_match else None,
        "location": location,
        "participants": [email["from"], MY_EMAIL],
        "source_message_id": email["id"],
    }

    print(f"[extract] date={details['date']} time={details['time']} location={details['location']}")
    return details


# ─────────────────────────────────────────────
#  Step 3: Compose unavailable reply
# ─────────────────────────────────────────────
def compose_unavailable_reply(email: dict[str, str], details: dict[str, Any]) -> str:
    date_str = details.get("date") or "המועד שהוצע"
    time_str = details.get("time") or ""
    when = f"{date_str} {time_str}".strip()

    return (
        f"שלום,\n\n"
        f"תודה על ההזמנה לפגישה.\n"
        f"בדקנו את היומן שלנו ולצערנו איננו פנויים ב-{when}.\n"
        f"נשמח לתאם מועד חלופי שיתאים לשני הצדדים.\n\n"
        f"בברכה,\n"
        f"יפת משולם ואדיר נחמיאס\n"
    )


# ─────────────────────────────────────────────
#  Calendar helpers
# ─────────────────────────────────────────────
def parse_datetime(date_str: str | None, time_str: str | None) -> Optional[datetime]:
    if not date_str or not time_str:
        return None

    date_str = date_str.replace("-", "/").replace(".", "/")
    for fmt in ["%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"]:
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
    busy = result["calendars"]["primary"].get("busy", [])
    return len(busy) == 0


def create_calendar_event(
    calendar_service, details: dict[str, Any], start_time: datetime, end_time: datetime
):
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


# ─────────────────────────────────────────────
#  Gmail – draft helper
# ─────────────────────────────────────────────
def create_unavailable_draft(
    gmail_service, original_email: dict[str, str], details: dict[str, Any]
):
    reply_body = compose_unavailable_reply(original_email, details)

    msg = EmailMessage()
    msg["To"] = original_email["from"]
    msg["Subject"] = f"Re: {original_email['subject']}"
    msg.set_content(reply_body)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = (
        gmail_service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return draft["id"]


# ─────────────────────────────────────────────
#  Main agent loop
# ─────────────────────────────────────────────
def run_agent():
    print("=" * 55)
    print("  Gmail & Calendar AI Agent — starting")
    print("=" * 55)

    creds = get_credentials()
    gmail_service, calendar_service = build_services(creds)

    email_ids = get_recent_email_ids(gmail_service, days=2, max_results=10)

    if not email_ids:
        print("No recent emails found.")
        return

    print(f"\nFound {len(email_ids)} recent emails.\n")

    for message_id in email_ids:
        email = get_message_text(gmail_service, message_id)
        print(f"{'─'*55}")
        print(f"Subject : {email['subject']}")
        print(f"From    : {email['from']}")

        # ── Step 1: Is this a meeting request? ────────────────
        if not detect_meeting_request(email):
            print("→ Not a meeting request. Skipping.\n")
            continue

        print("→ Meeting request detected!")

        # ── Step 2: Extract details ────────────────────────────
        details = extract_meeting_details(email)

        # ── Step 3: Parse date/time ────────────────────────────
        start_time = parse_datetime(details.get("date"), details.get("time"))

        if start_time is None:
            print("→ Could not determine date/time. Skipping calendar action.\n")
            continue

        end_time = start_time + timedelta(hours=1)
        print(f"→ Proposed time: {start_time.strftime('%d/%m/%Y %H:%M')}")

        # ── Step 4: Check calendar & act ──────────────────────
        if is_calendar_free(calendar_service, start_time, end_time):
            event_id, event_link = create_calendar_event(
                calendar_service, details, start_time, end_time
            )
            print(f"→ ✅ Calendar event created!")
            print(f"   ID   : {event_id}")
            print(f"   Link : {event_link}")
        else:
            draft_id = create_unavailable_draft(gmail_service, email, details)
            print(f"→ 📅 Calendar busy — unavailable reply draft created.")
            print(f"   Draft ID: {draft_id}")

        print()

    print("=" * 55)
    print("  Agent finished.")
    print("=" * 55)


if __name__ == "__main__":
    run_agent()
