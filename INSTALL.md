# AI Order Manager — ERPNext Install Guide

## What this app does
Listens to WhatsApp, Email, Instagram DMs → AI extracts order details → auto-creates Sales Order in ERPNext.

---

## Requirements
- ERPNext v14 or v15 (self-hosted or Frappe Cloud)
- Python 3.10+
- Anthropic API key (get from console.anthropic.com)
- WhatsApp Business API account (Meta for Developers)

---

## Step 1 — Install the App

SSH into your ERPNext server, then:

```bash
# Go to your bench folder (usually /home/frappe/frappe-bench)
cd /home/frappe/frappe-bench

# Get the app
bench get-app https://github.com/yourcompany/ai_order_manager
# OR copy the folder manually:
# cp -r /path/to/ai_order_manager apps/

# Install on your site
bench --site yoursite.com install-app ai_order_manager

# Run migrations (creates DocTypes in DB)
bench --site yoursite.com migrate

# Build assets
bench build --app ai_order_manager

# Restart
bench restart
```

---

## Step 2 — Configure Settings

1. In ERPNext, go to **AI Order Manager → AI Order Settings**
2. Fill in:

| Field | Value |
|-------|-------|
| Anthropic API Key | Your key from console.anthropic.com |
| Auto-Create SO Threshold | 0.75 (AI must be 75% confident to auto-create) |
| Default Item Code | An ERPNext Item to use when AI can't match |

---

## Step 3 — Connect WhatsApp

### In Meta for Developers (developers.facebook.com):
1. Create App → Business type
2. Add "WhatsApp" product
3. Go to WhatsApp → Configuration → Webhook
4. Set Webhook URL:
   ```
   https://yoursite.com/api/method/ai_order_manager.api.webhooks.whatsapp
   ```
5. Set Verify Token — any string you choose (e.g., `mySecret123`)
6. Subscribe to: `messages`

### Back in ERPNext AI Order Settings:
- WhatsApp Verify Token → `mySecret123` (same as above)
- WhatsApp App Secret → from Meta App Dashboard → Basic Settings
- WhatsApp Phone Number ID → from Meta dashboard
- WhatsApp Access Token → generate a permanent token in Meta

---

## Step 4 — Connect Email (Gmail)

1. In Gmail: Settings → Security → 2-Step Verification → App Passwords
2. Generate App Password for "Mail"
3. In ERPNext AI Order Settings:
   - Enable Email Polling ✓
   - Email Address → your@gmail.com
   - App Password → paste app password
   - IMAP Host → imap.gmail.com
   - IMAP Port → 993

Emails will be checked every 5 minutes automatically.

---

## Step 5 — Connect Instagram

1. In Meta for Developers, add "Messenger" product to your app
2. Connect your Instagram Business account
3. Webhook URL:
   ```
   https://yoursite.com/api/method/ai_order_manager.api.webhooks.instagram
   ```
4. Set Instagram Verify Token in ERPNext AI Order Settings

---

## Step 6 — Test It

In ERPNext → AI Order Manager → Test Message:
Paste this and click Test:
```
Hi, I want to order 5 kg of wheat flour and 2 kg of sugar.
Deliver to 123 MG Road, Mumbai by Friday.
My number is 9876543210.
```

You should see:
- AI extracts: customer, items, qty, delivery date
- Sales Order auto-created in ERPNext!

---

## Day-to-Day Usage

- **Order Inbox** → see all incoming messages, status, AI result
- **Filter by channel** → WhatsApp / Email / Instagram
- **Pending messages** → review and click "Create Sales Order"
- **Real-time alerts** → pop-up in ERPNext when AI creates SO

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Webhook not receiving | Check firewall, ensure site has SSL (https) |
| AI not extracting correctly | Lower threshold in settings, or re-run analysis |
| Email not polling | Check app password, IMAP enabled in Gmail |
| SO not created | Check Default Item Code is set in Settings |

---

## File Structure

```
ai_order_manager/
├── hooks.py                          ← App config, scheduler
├── setup.py                          ← pip install config
├── requirements.txt
└── ai_order_manager/
    ├── api/
    │   ├── webhooks.py               ← WhatsApp, Instagram endpoints
    │   └── actions.py                ← Form button actions
    ├── utils/
    │   ├── ai_engine.py              ← Claude AI extraction + SO creation
    │   └── email_poller.py           ← IMAP email reader
    ├── doctype/
    │   ├── order_inbox/              ← Inbox DocType
    │   └── ai_order_settings/        ← Settings DocType
    └── public/js/
        └── ai_order_manager.js       ← ERPNext UI enhancements
```
