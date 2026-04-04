"""
email_poller.py
───────────────
Called every 5 minutes by ERPNext scheduler.
Connects to your Gmail/Outlook/custom IMAP and reads unread emails.
Passes them through AI engine → creates Sales Orders.
"""

import frappe
import imaplib
import email as email_lib
from email.header import decode_header
import re
from ai_order_manager.utils.ai_engine import process_incoming_message


def poll_emails():
    """Main entry point called by scheduler."""
    settings = frappe.get_single("AI Order Settings")

    if not settings.email_polling_enabled:
        return

    try:
        _fetch_and_process(settings)
    except Exception as e:
        frappe.log_error(f"Email polling failed: {e}", "AI Order Manager")


def _fetch_and_process(settings):
    imap_host = settings.imap_host or "imap.gmail.com"
    imap_port = int(settings.imap_port or 993)
    email_addr = settings.polling_email
    password   = settings.polling_email_password   # Store encrypted in ERPNext

    if not email_addr or not password:
        return

    mail = imaplib.IMAP4_SSL(imap_host, imap_port)
    mail.login(email_addr, password)
    mail.select("inbox")

    # Fetch only UNSEEN emails
    status, data = mail.search(None, "UNSEEN")
    if status != "OK":
        return

    email_ids = data[0].split()
    processed = 0

    for eid in email_ids[-50:]:   # Max 50 per run
        try:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            raw_email   = msg_data[0][1]
            msg         = email_lib.message_from_bytes(raw_email)

            subject    = _decode_header_value(msg["Subject"]) or "(no subject)"
            from_field = _decode_header_value(msg["From"]) or ""
            sender_name, sender_email = _parse_from(from_field)
            body       = _extract_body(msg)

            full_text = f"Subject: {subject}\n\n{body}"

            process_incoming_message(
                message_text   = full_text,
                sender_name    = sender_name,
                sender_contact = sender_email,
                channel        = "Email",
                raw_payload    = {"subject": subject, "from": from_field}
            )

            # Mark as read
            mail.store(eid, "+FLAGS", "\\Seen")
            processed += 1

        except Exception as e:
            frappe.log_error(f"Error processing email {eid}: {e}", "AI Order Manager")

    mail.logout()
    frappe.logger().info(f"AI Order Manager: processed {processed} emails")


def _decode_header_value(value):
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result.strip()


def _parse_from(from_field):
    """Extract name and email from 'Name <email@x.com>'"""
    match = re.match(r"^(.*?)\s*<(.+?)>$", from_field)
    if match:
        return match.group(1).strip().strip('"'), match.group(2).strip()
    return from_field, from_field


def _extract_body(msg):
    """Get plain text body from email."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return body.strip()
