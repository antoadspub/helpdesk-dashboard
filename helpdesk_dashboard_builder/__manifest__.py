{
    "name": "Helpdesk Dashboard Builder",
    "summary": "Drag-and-drop configurable helpdesk dashboard for Odoo 18 CE",
    "version": "18.0.1.0.0",
    "category": "Services/Helpdesk",
    "depends": ["base", "web", "mail", "helpdesk_mgmt"],
    "data": [
        "security/ir.model.access.csv",
        "views/helpdesk_dashboard_layout_views.xml",
        "views/helpdesk_dashboard_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "helpdesk_dashboard_builder/static/src/scss/dashboard_builder.scss",
            "helpdesk_dashboard_builder/static/src/js/dashboard_builder_action.js",
            "helpdesk_dashboard_builder/static/src/xml/dashboard_builder_action.xml",
        ],
    },
    "license": "LGPL-3",
    "application": False,
    "installable": True,
}
