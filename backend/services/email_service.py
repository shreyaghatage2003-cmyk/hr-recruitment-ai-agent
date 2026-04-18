import asyncio
import logging
from backend.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Async wrapper around SendGrid. Falls back to log-only mode if key not configured."""

    def __init__(self):
        self._client = None
        if settings.has_sendgrid:
            try:
                from sendgrid import SendGridAPIClient
                self._client = SendGridAPIClient(settings.sendgrid_api_key)
            except Exception as e:
                logger.warning(f"SendGrid init failed: {e}")

    async def send(self, to: str, subject: str, html_body: str) -> bool:
        if not self._client:
            logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}")
            return True  # pretend success so pipeline continues
        try:
            from sendgrid.helpers.mail import Mail
            message = Mail(
                from_email=settings.sendgrid_from_email,
                to_emails=to,
                subject=subject,
                html_content=html_body,
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._client.send(message))
            return True
        except Exception as e:
            logger.error(f"Email send failed to {to}: {e}")
            return False

    async def send_rejection(self, candidate_name: str, candidate_email: str, role_title: str) -> bool:
        subject = f"Your application for {role_title}"
        body = f"""
        <p>Dear {candidate_name},</p>
        <p>Thank you for applying for the <strong>{role_title}</strong> position.</p>
        <p>After reviewing your application, we regret to inform you that we will not be moving forward at this time.</p>
        <p>We wish you the best in your job search.</p>
        <p>Best regards,<br>HR Team</p>
        """
        return await self.send(candidate_email, subject, body)

    async def send_interview_invite(self, candidate_name: str, candidate_email: str, role_title: str) -> bool:
        subject = f"Interview Invitation — {role_title}"
        body = f"""
        <p>Dear {candidate_name},</p>
        <p>Congratulations! You have been shortlisted for the <strong>{role_title}</strong> role.</p>
        <p>Please complete your technical interview by clicking the link in your dashboard.</p>
        <p>Best regards,<br>HR Team</p>
        """
        return await self.send(candidate_email, subject, body)

    async def send_schedule_confirmation(
        self,
        candidate_name: str,
        candidate_email: str,
        role_title: str,
        meeting_link: str,
        interview_datetime: str,
    ) -> bool:
        subject = f"Interview Scheduled — {role_title}"
        body = f"""
        <p>Dear {candidate_name},</p>
        <p>Your interview for <strong>{role_title}</strong> has been scheduled.</p>
        <p><strong>Date/Time:</strong> {interview_datetime}</p>
        <p><strong>Meeting Link:</strong> <a href="{meeting_link}">{meeting_link}</a></p>
        <p>Best regards,<br>HR Team</p>
        """
        return await self.send(candidate_email, subject, body)

    async def send_hr_notification(
        self,
        candidate_name: str,
        role_title: str,
        interview_datetime: str,
        meeting_link: str,
    ) -> bool:
        subject = f"Interview Scheduled: {candidate_name} — {role_title}"
        body = f"""
        <p>An interview has been scheduled.</p>
        <p><strong>Candidate:</strong> {candidate_name}</p>
        <p><strong>Role:</strong> {role_title}</p>
        <p><strong>Date/Time:</strong> {interview_datetime}</p>
        <p><strong>Meeting Link:</strong> <a href="{meeting_link}">{meeting_link}</a></p>
        """
        return await self.send(settings.hr_email, subject, body)


email_service = EmailService()
