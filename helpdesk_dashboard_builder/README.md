# Helpdesk Dashboard Builder (Odoo 18 CE)

This module adds a configurable Helpdesk dashboard for managers:

- Drag-and-drop widget ordering
- Widget sizing (full / half / third width)
- Per-widget period filtering
- Widget types: counter, chart, table, activity feed
- Layout scope: user-specific or global

## Usage

1. Go to **Helpdesk Dashboard > Layouts** and create a layout.
2. Add widgets and configure their fields.
3. Open **Helpdesk Dashboard > Dashboard** to use the drag-and-drop view.

## Notes

- The module depends on `helpdesk_mgmt` from OCA Helpdesk.
- Widgets read from the configured `model_name` (default: `helpdesk.ticket`).
