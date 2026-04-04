app_name = "ai_order_manager"
app_title = "AI Order Manager"
app_publisher = "Your Company"
app_description = "Auto-create Sales Orders from WhatsApp, Email, Instagram, LinkedIn messages using AI"
app_icon = "octicon octicon-robot"
app_color = "#4f46e5"
app_email = "admin@yourcompany.com"
app_license = "MIT"
app_version = "1.0.0"

# ─── Scheduled Jobs ───────────────────────────────────────────────────────────
scheduler_events = {
    "cron": {
        # Poll email every 5 minutes
        "*/5 * * * *": [
            "ai_order_manager.utils.email_poller.poll_emails"
        ],
    },
    "all": [
        "ai_order_manager.utils.cleanup.cleanup_old_logs"
    ]
}

# ─── Webhooks exposed ──────────────────────────────────────────────────────────
# WhatsApp Business API will POST here
# Instagram Graph API will POST here

# ─── Permission Queries ───────────────────────────────────────────────────────
permission_query_conditions = {}

# ─── Document Events ─────────────────────────────────────────────────────────
doc_events = {
    "Sales Order": {
        "on_submit": "ai_order_manager.utils.notifier.notify_so_created"
    }
}

# ─── Website ─────────────────────────────────────────────────────────────────
website_route_rules = [
    {"from_route": "/ai-orders", "to_route": "ai_order_manager"},
]

# ─── JS/CSS assets ────────────────────────────────────────────────────────────
app_include_js  = ["ai_order_manager/js/ai_order_manager.js"]
app_include_css = ["ai_order_manager/css/ai_order_manager.css"]
