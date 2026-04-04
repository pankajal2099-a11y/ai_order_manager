/* ai_order_manager.js — loaded in ERPNext */

frappe.provide("ai_order_manager");

// ── Real-time notification when a new SO is created by AI ──────────────────
frappe.realtime.on("ai_order_created", function(data) {
    frappe.show_alert({
        message: `🤖 AI created Sales Order <b>${data.so_name}</b> for ${data.customer}`,
        indicator: "green"
    }, 8);
});


// ── Custom List View for Order Inbox ──────────────────────────────────────
frappe.listview_settings["Order Inbox"] = {
    add_fields: ["status", "channel", "is_order", "ai_confidence", "sales_order"],
    get_indicator(doc) {
        const map = {
            "Pending":      ["orange",  "status,=,Pending"],
            "AI Processed": ["blue",    "status,=,AI Processed"],
            "SO Created":   ["green",   "status,=,SO Created"],
            "Rejected":     ["gray",    "status,=,Rejected"],
            "Error":        ["red",     "status,=,Error"],
        };
        return map[doc.status] || ["gray", ""];
    },
    onload(listview) {
        listview.page.add_inner_button("Process Selected", function() {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint("Select at least one message.");
                return;
            }
            frappe.confirm(
                `Create Sales Orders for ${selected.length} selected message(s)?`,
                () => {
                    selected.forEach(row => {
                        frappe.call({
                            method: "ai_order_manager.api.actions.manually_create_so",
                            args: { inbox_name: row.name },
                            callback(r) {
                                if (r.message && r.message.sales_order) {
                                    frappe.show_alert({ message: `SO ${r.message.sales_order} created`, indicator: "green" });
                                }
                            }
                        });
                    });
                    listview.refresh();
                }
            );
        });
    }
};


// ── Custom Form for Order Inbox ────────────────────────────────────────────
frappe.ui.form.on("Order Inbox", {
    refresh(frm) {
        // Show AI extracted data nicely
        if (frm.doc.ai_result) {
            try {
                const data = JSON.parse(frm.doc.ai_result);
                frm.set_df_property("ai_result", "description",
                    `Confidence: ${(data.confidence * 100).toFixed(0)}% | Items: ${(data.items || []).length}`
                );
            } catch(e) {}
        }

        // Action buttons
        if (frm.doc.status !== "SO Created") {
            frm.add_custom_button("Create Sales Order", function() {
                frappe.call({
                    method: "ai_order_manager.api.actions.manually_create_so",
                    args: { inbox_name: frm.doc.name },
                    freeze: true,
                    freeze_message: "Creating Sales Order...",
                    callback(r) {
                        if (r.message && r.message.sales_order) {
                            frappe.msgprint(`Sales Order <b>${r.message.sales_order}</b> created successfully!`);
                            frm.reload_doc();
                        }
                    }
                });
            }, "Actions").addClass("btn-primary");

            frm.add_custom_button("Re-run AI Analysis", function() {
                frappe.call({
                    method: "ai_order_manager.api.actions.reanalyze",
                    args: { inbox_name: frm.doc.name },
                    freeze: true,
                    freeze_message: "Running AI analysis...",
                    callback(r) {
                        frm.reload_doc();
                    }
                });
            }, "Actions");

            frm.add_custom_button("Reject", function() {
                frappe.db.set_value("Order Inbox", frm.doc.name, "status", "Rejected")
                    .then(() => frm.reload_doc());
            }, "Actions");
        }

        if (frm.doc.sales_order) {
            frm.add_custom_button("View Sales Order", function() {
                frappe.set_route("Form", "Sales Order", frm.doc.sales_order);
            }).addClass("btn-success");
        }

        // Channel badge color
        const channelColors = {
            WhatsApp:  "#25D366",
            Email:     "#4285F4",
            Instagram: "#E1306C",
            LinkedIn:  "#0077B5",
            Twitter:   "#1DA1F2",
        };
        const color = channelColors[frm.doc.channel] || "#888";
        frm.page.set_indicator(frm.doc.channel, color);
    }
});


// ── Workspace shortcut — AI Order Dashboard ────────────────────────────────
frappe.pages["ai-order-dashboard"] = {
    title: "AI Order Dashboard",
    icon: "robot",
};
