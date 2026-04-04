import frappe

def cleanup_old_logs():
    """Delete AI logs older than 90 days."""
    frappe.db.delete("Order Inbox", {
        "status": ["in", ["Rejected", "Error"]],
        "received_at": ["<", frappe.utils.add_days(frappe.utils.today(), -90)]
    })
    frappe.db.commit()
