"""
Legacy SMTP sender — kept for backward compatibility.

``steely.smtp.SendEmail`` predates the provider-based :mod:`steely.email`
subsystem and is still imported directly by existing consumers, e.g.::

    from steely.smtp import SendEmail

Its public surface is frozen: constructor ``(login, password, smtp_server,
smtp_port, sender=None, destination=None)``, ``check_config() -> bool`` and
``send_email(subject, message, destination=None) -> dict``. Do not change these
signatures or return values without a major version bump.

Internally it now delegates to :class:`steely.email.providers.smtp.SMTPProvider`
so there is a single SMTP implementation in the library. The observable
behaviour is preserved: the ``From`` header and envelope sender are the login
address (matching the original), ``send_email`` returns
``{"message": "Email Successfully Sent"}`` and raises on failure.

New code should prefer :class:`steely.email.EmailClient` /
:class:`steely.email.EmailMessage` instead of this class.
"""
from steely.email.message import EmailMessage
from steely.email.providers.smtp import SMTPProvider


class SendEmail:
    """Backward-compatible SMTP email sender (thin wrapper over SMTPProvider)."""

    def __init__(self, login, password, smtp_server, smtp_port, sender=None, destination=None):
        self.login = login
        self.password = password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.destination = destination
        self._provider = SMTPProvider(
            server=smtp_server,
            port=smtp_port,
            username=login,
            password=password,
            use_tls=True,
            from_email=login,
        )

    def check_config(self):
        """Return ``True`` when the SMTP server accepts the credentials.

        Raises ``Exception`` on failure, matching the original behaviour.
        """
        if self._provider.validate():
            return True
        raise Exception(
            "Your smtp looks fine, maybe the problem is on your login information."
        )

    def send_email(self, subject, message, destination=None):
        """Send an HTML email. ``message`` is the HTML body.

        Returns ``{"message": "Email Successfully Sent"}`` on success and raises
        ``Exception`` on failure, preserving the original contract.
        """
        target = destination if destination is not None else self.destination
        to = [target] if isinstance(target, str) else list(target)
        # from_email=self.login mirrors the original: the ``From`` header and
        # envelope sender are always the login address (the ``sender`` argument
        # was accepted but unused historically).
        result = self._provider.send(
            EmailMessage(to=to, subject=subject, body_html=message),
            from_email=self.login,
        )
        if not result.success:
            raise Exception(result.message)
        return {"message": "Email Successfully Sent"}
