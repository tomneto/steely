"""
Send an email through the Resend HTTP API with steely.email.

Requires the optional dependency:
    pip install "steely[http]"

Run:
    export RESEND_API_KEY=re_xxx
    export RESEND_FROM=noreply@your-verified-domain.com
    export RESEND_TO=you@example.com
    python examples/email_resend.py

Swapping SMTP <-> Resend is a one-line change: only the EmailClient(...) call
differs; the EmailMessage and the EmailResult handling stay identical.
"""
import os

from steely.email import EmailClient, EmailMessage


def main() -> None:
    client = EmailClient(
        "resend",
        api_key=os.environ["RESEND_API_KEY"],
        from_email=os.environ.get("RESEND_FROM", "noreply@example.com"),
    )

    message = EmailMessage(
        to=[os.environ.get("RESEND_TO", "dest@example.com")],
        subject="Hello from steely.email (Resend)",
        body_html="<h1>Hello</h1><p>Sent via ResendProvider.</p>",
        body_text="Hello — sent via ResendProvider.",
    )

    result = client.send(message)
    print("provider  :", result.provider)
    print("success   :", result.success)
    print("message_id:", result.message_id)
    print("status    :", result.status_code)
    if not result.success:
        print("error     :", result.message)


if __name__ == "__main__":
    main()
