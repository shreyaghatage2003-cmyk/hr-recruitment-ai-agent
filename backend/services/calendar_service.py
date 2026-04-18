import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CalendarService:
    """
    Google Calendar integration for scheduling interviews.
    Falls back to a generated meet link if credentials are unavailable.
    Justification: Google Calendar is free, widely used, and has a well-documented Python SDK.
    """

    def __init__(self):
        self._service = None
        self._try_init()

    def _try_init(self):
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            from backend.config import settings

            if settings.google_calendar_credentials_json:
                creds = Credentials.from_service_account_file(
                    settings.google_calendar_credentials_json,
                    scopes=["https://www.googleapis.com/auth/calendar"],
                )
                self._service = build("calendar", "v3", credentials=creds)
        except Exception as e:
            logger.warning(f"Google Calendar init failed, using fallback: {e}")

    async def create_meeting(
        self,
        title: str,
        start_dt: datetime,
        attendee_emails: list[str],
        duration_minutes: int = 60,
    ) -> dict:
        if self._service:
            return await self._create_google_event(title, start_dt, attendee_emails, duration_minutes)
        return self._generate_fallback_link(start_dt)

    async def _create_google_event(self, title: str, start_dt: datetime, attendees: list[str], duration: int) -> dict:
        end_dt = start_dt + timedelta(minutes=duration)
        event = {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": e} for e in attendees],
            "conferenceData": {
                "createRequest": {"requestId": str(uuid.uuid4()), "conferenceSolutionKey": {"type": "hangoutsMeet"}}
            },
        }
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._service.events()
                .insert(calendarId="primary", body=event, conferenceDataVersion=1)
                .execute(),
            )
            meet_link = result.get("hangoutLink", self._generate_fallback_link(start_dt)["link"])
            return {"link": meet_link, "event_id": result.get("id")}
        except Exception as e:
            logger.error(f"Google Calendar event creation failed: {e}")
            return self._generate_fallback_link(start_dt)

    def _generate_fallback_link(self, start_dt: datetime) -> dict:
        token = uuid.uuid4().hex[:10]
        return {"link": f"https://meet.jit.si/hr-interview-{token}", "event_id": None}


calendar_service = CalendarService()
