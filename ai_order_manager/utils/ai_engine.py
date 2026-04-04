"""
ai_engine.py
────────────
Sends raw message text to Claude AI → gets structured order data back
→ creates ERPNext Sales Order automatically
"""

import frappe
import anthropic
import json
from datetime import datetime


def get_api_key():
    settings = frappe.get_single("AI Order Settings")
    return settings.anthropic_api_key


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — Extract order details from raw message text
# ──────────────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are an order extraction AI for an ERP system.

Given a raw customer message (WhatsApp, Email, Instagram DM, etc.), extract order details.

Respond ONLY in this exact JSON format, no explanation:
{
  "is_order": true/false,
  "customer_name": "name or null",
  "customer_phone": "phone or null",
  "customer_email": "email or null",
  "items": [
    {"item_name": "product name", "qty": 1, "rate": 0.0, "description": "any notes"}
  ],
  "delivery_date": "YYYY-MM-DD or null",
  "delivery_address": "address or null",
  "special_instructions": "any special notes or null",
  "currency": "INR",
  "confidence": 0.0
}

Rules:
- Set is_order=false if message is inquiry, complaint, or non-order
- confidence is 0.0 to 1.0 — how sure are you this is a real order
- If price not mentioned, set rate to 0.0
- Always respond with valid JSON only
"""

def extract_order_from_message(message_text: str, sender_name: str = "", channel: str = "") -> dict:
    """
    Use Claude AI to extract order details from a raw message.
    Returns parsed dict.
    """
    client = anthropic.Anthropic(api_key=get_api_key())

    user_content = f"""Channel: {channel}
Sender: {sender_name}
Message:
{message_text}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    except Exception as e:
        frappe.log_error(f"AI extraction failed: {e}", "AI Order Manager")
        return {"is_order": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — Create or fetch Customer in ERPNext
# ──────────────────────────────────────────────────────────────────────────────

def get_or_create_customer(order_data: dict) -> str:
    """Return customer name (create if not exists)."""
    name  = order_data.get("customer_name") or "Walk-in Customer"
    phone = order_data.get("customer_phone")
    email = order_data.get("customer_email")

    # Try match by phone first
    if phone:
        existing = frappe.db.get_value("Customer", {"mobile_no": phone}, "name")
        if existing:
            return existing

    # Try match by email
    if email:
        existing = frappe.db.get_value("Contact Email",
            {"email_id": email, "parenttype": "Contact"}, "parent")
        if existing:
            contact = frappe.get_doc("Contact", existing)
            if contact.links:
                for link in contact.links:
                    if link.link_doctype == "Customer":
                        return link.link_name

    # Create new customer
    customer = frappe.new_doc("Customer")
    customer.customer_name  = name
    customer.customer_type  = "Individual"
    customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"
    customer.territory      = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
    if phone:
        customer.mobile_no = phone
    customer.insert(ignore_permissions=True)
    frappe.db.commit()
    return customer.name


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — Create Sales Order in ERPNext
# ──────────────────────────────────────────────────────────────────────────────

def create_sales_order(order_data: dict, inbox_doc_name: str = None) -> str:
    """
    Create ERPNext Sales Order from extracted order data.
    Returns the SO name like 'SAL-ORD-2025-00042'
    """
    customer_name = get_or_create_customer(order_data)

    so = frappe.new_doc("Sales Order")
    so.customer        = customer_name
    so.order_type      = "Sales"
    so.currency        = order_data.get("currency", "INR")
    so.transaction_date = frappe.utils.today()

    # Delivery date
    delivery = order_data.get("delivery_date")
    so.delivery_date = delivery if delivery else frappe.utils.add_days(frappe.utils.today(), 7)

    if order_data.get("delivery_address"):
        so.shipping_address_name = order_data["delivery_address"]

    # Line items
    items = order_data.get("items", [])
    if not items:
        items = [{"item_name": "General Order", "qty": 1, "rate": 0.0, "description": "Auto-created by AI Order Manager"}]

    for item in items:
        # Try to find matching item in ERPNext
        item_code = frappe.db.get_value("Item", {"item_name": item["item_name"]}, "name")
        if not item_code:
            # Use a default item or create new
            item_code = frappe.db.get_single_value("AI Order Settings", "default_item_code") or "MISC-ITEM"

        so.append("items", {
            "item_code": item_code,
            "item_name": item.get("item_name", item_code),
            "description": item.get("description", item.get("item_name", "")),
            "qty": item.get("qty", 1),
            "rate": item.get("rate", 0.0),
            "delivery_date": so.delivery_date,
        })

    if order_data.get("special_instructions"):
        so.terms = order_data["special_instructions"]

    # Custom field to track source
    if inbox_doc_name:
        so.ai_order_source = inbox_doc_name   # custom field added via our DocType

    so.insert(ignore_permissions=True)
    frappe.db.commit()

    # Update the inbox message doc
    if inbox_doc_name:
        frappe.db.set_value("Order Inbox", inbox_doc_name, {
            "status": "SO Created",
            "sales_order": so.name
        })
        frappe.db.commit()

    frappe.publish_realtime(
        "ai_order_created",
        {"so_name": so.name, "customer": customer_name},
        user=frappe.session.user
    )

    return so.name


# ──────────────────────────────────────────────────────────────────────────────
# MASTER FUNCTION — call this with any raw message
# ──────────────────────────────────────────────────────────────────────────────

def process_incoming_message(
    message_text: str,
    sender_name: str,
    sender_contact: str,
    channel: str,          # "WhatsApp" | "Email" | "Instagram" | "LinkedIn" | "Twitter"
    raw_payload: dict = None,
    auto_create: bool = True
) -> dict:
    """
    Full pipeline:
    1. Save message to Order Inbox
    2. AI extracts order details
    3. If is_order and confidence >= threshold → create SO
    Returns summary dict
    """
    # Save to inbox
    inbox = frappe.new_doc("Order Inbox")
    inbox.sender_name    = sender_name
    inbox.sender_contact = sender_contact
    inbox.channel        = channel
    inbox.message_text   = message_text
    inbox.received_at    = datetime.now()
    inbox.status         = "Pending"
    inbox.raw_payload    = json.dumps(raw_payload or {})
    inbox.insert(ignore_permissions=True)
    frappe.db.commit()

    # AI extraction
    order_data = extract_order_from_message(message_text, sender_name, channel)

    # Save AI result back to inbox
    frappe.db.set_value("Order Inbox", inbox.name, {
        "ai_result": json.dumps(order_data),
        "is_order": order_data.get("is_order", False),
        "ai_confidence": order_data.get("confidence", 0.0),
        "status": "AI Processed"
    })
    frappe.db.commit()

    # Read threshold from settings
    settings  = frappe.get_single("AI Order Settings")
    threshold = settings.auto_create_threshold or 0.75

    so_name = None
    if auto_create and order_data.get("is_order") and order_data.get("confidence", 0) >= threshold:
        try:
            so_name = create_sales_order(order_data, inbox_doc_name=inbox.name)
        except Exception as e:
            frappe.db.set_value("Order Inbox", inbox.name, {"status": "Error", "error_log": str(e)})
            frappe.db.commit()
            frappe.log_error(f"SO creation failed: {e}", "AI Order Manager")

    return {
        "inbox_id": inbox.name,
        "is_order": order_data.get("is_order"),
        "confidence": order_data.get("confidence"),
        "sales_order": so_name,
        "order_data": order_data
    }
