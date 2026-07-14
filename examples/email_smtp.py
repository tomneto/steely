"""
Send an email over SMTP with steely.email (standard library, no extra install).

Run:
    python examples/email_smtp.py

Set real credentials via environment variables first, e.g.:
    export SMTP_SERVER=smtp.hostinger.com
    export SMTP_PORT=587
    export SMTP_USER=noreply@acme.com
    export SMTP_PASSWORD=…
    export SMTP_TO=you@example.com
"""
import os

from steely.email import EmailClient, EmailMessage


def main() -> None:
    client = EmailClient(
        "smtp",
        server=os.environ.get("SMTP_SERVER", "localhost"),
        port=int(os.environ.get("SMTP_PORT", "587")),
        username=os.environ.get("SMTP_USER"),
        password=os.environ.get("SMTP_PASSWORD"),
        use_tls=True,
    )

    message = EmailMessage(
        to=[os.environ.get("SMTP_TO", "dest@example.com")],
        subject="Hello from steely.email (SMTP)",
        body_html="<h1>Hello</h1><p>Sent via SMTPProvider.</p>",
        body_text="Hello — sent via SMTPProvider.",
    )

    result = client.send(message)
    print("provider:", result.provider)
    print("success :", result.success)
    print("message :", result.message)


if __name__ == "__main__":
    main()
