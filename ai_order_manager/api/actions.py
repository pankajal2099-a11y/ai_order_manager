"""
api/actions.py
──────────────
Called from ERPNext form buttons (not webhooks).
"""

import frappe
import json
from ai_order_manager.utils.ai_engine import (
    extract_order_from_message,
    create_sales_order,
    process_incoming_message
)


@frappe.whitelist()
def manually_create_so(inbox_name: str):
    """
    Manually trigger SO creation from Order Inbox form.
    Called by 'Create Sales Order' button.
    """
    doc = frappe.get_doc("Order Inbox", inbox_name)

    if doc.status == "SO Created":
        frappe.throw("Sales Order already created for this message.")

    # Use stored AI result if available, else re-run AI
    if doc.ai_result:
        order_data = json.loads(doc.ai_result)
    else:
        order_data = extract_order_from_message(
            doc.message_text, doc.sender_name, doc.channel
        )
        frappe.db.set_value("Order Inbox", inbox_name, "ai_result", json.dumps(order_data))

    so_name = create_sales_order(order_data, inbox_doc_name=inbox_name)
    return {"sales_order": so_name, "order_data": order_data}


@frappe.whitelist()
def reanalyze(inbox_name: str):
    """Re-run AI analysis on message."""
    doc = frappe.get_doc("Order Inbox", inbox_name)
    order_data = extract_order_from_message(
        doc.message_text, doc.sender_name, doc.channel
    )
    frappe.db.set_value("Order Inbox", inbox_name, {
        "ai_result":     json.dumps(order_data),
        "is_order":      order_data.get("is_order", False),
        "ai_confidence": order_data.get("confidence", 0.0),
        "status":        "AI Processed"
    })
    frappe.db.commit()
    return order_data


@frappe.whitelist()
def test_message(message_text: str, channel: str = "WhatsApp"):
    """
    Test endpoint — paste any message and see what AI extracts.
    Useful during setup.
    """
    from ai_order_manager.utils.ai_engine import extract_order_from_message
    result = extract_order_from_message(message_text, "Test Sender", channel)
    return result


@frappe.whitelist()
def get_dashboard_stats():
    """Stats for the workspace dashboard."""
    return {
        "total_today": frappe.db.count("Order Inbox", filters={
            "received_at": [">=", frappe.utils.today()]
        }),
        "so_created_today": frappe.db.count("Order Inbox", filters={
            "status": "SO Created",
            "received_at": [">=", frappe.utils.today()]
        }),
        "pending": frappe.db.count("Order Inbox", filters={"status": "Pending"}),
        "errors":  frappe.db.count("Order Inbox", filters={"status": "Error"}),
        "channels": frappe.db.sql("""
            SELECT channel, COUNT(*) as cnt
            FROM `tabOrder Inbox`
            WHERE DATE(received_at) = CURDATE()
            GROUP BY channel
        """, as_dict=True),
    }
