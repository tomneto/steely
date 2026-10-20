"""
SMTPProvider — delivery over SMTP using the Python standard library only
(no third-party dependencies).

Opens a fresh connection per :meth:`send`, so a single instance is safe to
share across threads. Builds a ``multipart/alternative`` message so a
plain-text fallback can accompany the HTML body; when the message carries
attachments the alternative part is wrapped in a ``multipart/mixed`` root and
each :class:`~steely.email.message.Attachment` becomes its own MIME part
(``Content-Disposition: inline`` with a ``Content-ID`` for inline parts).
"""
from __future__ import annotations

import smtplib
from email.message import MIMEPart
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

from steely.email.message import EmailMessage
from steely.email.providers.base import EmailProvider
from steely.email.result import EmailResult
from steely.logger import Logger


class SMTPProvider(EmailProvider):
    """Send email through an SMTP server.

    Parameters
    ----------
    server, port:
        SMTP host and port (e.g. ``"smtp.hostinger.com"``, ``587``).
    username, password:
        Login credentials. If both are omitted the provider connects without
        authenticating (useful for local relays / debugging servers).
    use_tls:
        Issue ``STARTTLS`` after connecting (default ``True``).
    timeout:
        Socket timeout in seconds.
    from_email:
        Default sender used when a message doesn't specify ``from_email``.
        Falls back to ``username``.
    """

    def __init__(
        self,
        server: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        timeout: int = 30,
        from_email: str | None = None,
    ) -> None:
        self.server = server
        self.port = int(port)
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout
        self.from_email = from_email or username
        self.__logger__ = Logger(
            app_name=self.__class__.__name__, owner=str(username or server)
        ).log

    @property
    def name(self) -> str:
        return "smtp"

    @staticmethod
    def _attachment_part(attachment: Any) -> MIMEPart:
        """Build one MIME part for an :class:`Attachment`."""
        maintype, subtype = attachment.mime_parts()
        part = MIMEPart()
        if attachment.inline:
            part.set_content(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
                disposition="inline",
                cid=f"<{attachment.content_id}>" if attachment.content_id else None,
            )
        else:
            part.set_content(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )
        return part

    def _build(
        self, message: EmailMessage, from_email: str | None
    ) -> tuple[MIMEMultipart, str]:
        sender = message.from_email or from_email or self.from_email or self.username

        body = MIMEMultipart("alternative")
        # For multipart/alternative the last part is the preferred one, so the
        # plain-text fallback goes first and the HTML body last.
        if message.body_text:
            body.attach(MIMEText(message.body_text, "plain"))
        if message.body_html:
            body.attach(MIMEText(message.body_html, "html"))
        elif not message.body_text:
            body.attach(MIMEText("", "plain"))

        if message.attachments:
            msg = MIMEMultipart("mixed")
            msg.attach(body)
            for attachment in message.attachments:
                msg.attach(self._attachment_part(attachment))
        else:
            msg = body

        msg["Subject"] = message.subject
        msg["From"] = formataddr((message.from_name, sender)) if message.from_name else sender
        msg["To"] = ", ".join(message.to)
        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        if message.reply_to:
            msg["Reply-To"] = message.reply_to
        if message.headers:
            for key, value in message.headers.items():
                msg[key] = value

        return msg, sender

    def _connect(self) -> smtplib.SMTP:
        server = smtplib.SMTP(self.server, self.port, timeout=self.timeout)
        if self.use_tls:
            server.starttls()
        if self.username and self.password:
            server.login(self.username, self.password)
        return server

    def send(
        self, message: EmailMessage, from_email: str | None = None, **kwargs: Any
    ) -> EmailResult:
        try:
            msg, sender = self._build(message, from_email)
            server = self._connect()
            try:
                self.__logger__("start", "Connected to SMTP server")
                server.sendmail(sender, message.recipients(), msg.as_string())
                self.__logger__("success", "Email Successfully Sent")
            finally:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001 - best-effort close
                    pass
            return EmailResult(success=True, message="Email Successfully Sent", provider=self.name)
        except Exception as exc:  # noqa: BLE001 - surfaced as a result
            self.__logger__("error", f"Error sending email: {exc}")
            return EmailResult(
                success=False, message=f"Error sending email: {exc}", provider=self.name
            )

    def validate(self) -> bool:
        try:
            server = smtplib.SMTP(self.server, self.port, timeout=self.timeout)
            try:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
            finally:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001
                    pass
            return True
        except Exception as exc:  # noqa: BLE001
            self.__logger__("error", f"SMTP validate failed: {exc}")
            return False
