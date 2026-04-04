"""
api/webhooks.py
───────────────
Public webhook endpoints. Register these URLs in:
  - WhatsApp Business API dashboard
  - Instagram Graph API
  - LinkedIn Marketing API
  - Any SMTP/IMAP forwarder

All routes are under:  https://yourerp.com/api/method/ai_order_manager.api.webhooks.*
"""

import frappe
import json
import hmac
import hashlib
from ai_order_manager.utils.ai_engine import process_incoming_message


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP BUSINESS API
# Webhook URL: /api/method/ai_order_manager.api.webhooks.whatsapp
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def whatsapp():
    """Handles both GET (verification) and POST (message receive) from WhatsApp."""
    if frappe.request.method == "GET":
        # WhatsApp sends hub.challenge to verify your webhook
        params = frappe.request.args
        mode      = params.get("hub.mode")
        token     = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        settings = frappe.get_single("AI Order Settings")
        if mode == "subscribe" and token == settings.whatsapp_verify_token:
            frappe.response["type"] = "text"
            frappe.response["result"] = challenge
            return

        frappe.throw("Verification failed", frappe.PermissionError)

    # POST — incoming message
    payload = json.loads(frappe.request.data)
    _verify_whatsapp_signature(frappe.request)

    try:
        entry   = payload["entry"][0]
        changes = entry["changes"][0]["value"]

        if "messages" not in changes:
            return {"status": "no message"}

        msg     = changes["messages"][0]
        contact = changes["contacts"][0]

        sender_name    = contact.get("profile", {}).get("name", "Unknown")
        sender_phone   = msg["from"]
        message_type   = msg["type"]

        # Extract text (handle text, image caption, etc.)
        if message_type == "text":
            text = msg["text"]["body"]
        elif message_type == "image":
            text = msg.get("image", {}).get("caption", "")
        elif message_type == "document":
            text = msg.get("document", {}).get("caption", "")
        else:
            return {"status": "unsupported message type"}

        if not text:
            return {"status": "empty message"}

        result = process_incoming_message(
            message_text   = text,
            sender_name    = sender_name,
            sender_contact = sender_phone,
            channel        = "WhatsApp",
            raw_payload    = payload
        )
        return result

    except Exception as e:
        frappe.log_error(f"WhatsApp webhook error: {e}", "AI Order Manager")
        return {"status": "error", "message": str(e)}


def _verify_whatsapp_signature(request):
    """Verify X-Hub-Signature-256 from Meta."""
    settings  = frappe.get_single("AI Order Settings")
    secret    = settings.whatsapp_app_secret
    if not secret:
        return  # Skip verification if not configured

    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not sig_header.startswith("sha256="):
        frappe.throw("Invalid signature", frappe.PermissionError)

    expected = hmac.new(secret.encode(), request.data, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={expected}", sig_header):
        frappe.throw("Signature mismatch", frappe.PermissionError)


# ─────────────────────────────────────────────────────────────────────────────
# INSTAGRAM / FACEBOOK GRAPH API
# Webhook URL: /api/method/ai_order_manager.api.webhooks.instagram
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def instagram():
    """Instagram DMs and comments via Facebook Graph API."""
    if frappe.request.method == "GET":
        params    = frappe.request.args
        token     = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        settings  = frappe.get_single("AI Order Settings")
        if token == settings.instagram_verify_token:
            frappe.response["type"] = "text"
            frappe.response["result"] = challenge
            return
        frappe.throw("Verification failed", frappe.PermissionError)

    payload = json.loads(frappe.request.data)
    try:
        for entry in payload.get("entry", []):
            for messaging in entry.get("messaging", []):
                msg    = messaging.get("message", {})
                text   = msg.get("text", "")
                sender = messaging.get("sender", {}).get("id", "unknown")

                if text:
                    process_incoming_message(
                        message_text   = text,
                        sender_name    = f"Instagram User {sender}",
                        sender_contact = sender,
                        channel        = "Instagram",
                        raw_payload    = payload
                    )
        return {"status": "ok"}
    except Exception as e:
        frappe.log_error(f"Instagram webhook error: {e}", "AI Order Manager")
        return {"status": "error"}


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC WEBHOOK — for any custom source (Telegram, SMS, etc.)
# POST JSON: { "sender_name": "", "sender_contact": "", "channel": "", "message": "" }
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def generic():
    """Generic webhook — integrate any channel with a simple POST."""
    payload = json.loads(frappe.request.data)
    result  = process_incoming_message(
        message_text   = payload.get("message", ""),
        sender_name    = payload.get("sender_name", "Unknown"),
        sender_contact = payload.get("sender_contact", ""),
        channel        = payload.get("channel", "Other"),
        raw_payload    = payload
    )
    return result
