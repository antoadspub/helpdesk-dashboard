# Helpdesk Dashboard Builder (Odoo 18 CE)

This module adds a configurable Helpdesk dashboard for managers with drag-and-drop layout control.

## Widget metrics included

Each metric can be shown as **Counter** or **Chart**:

- Assigned engineer active tickets
- Assigned engineer closed tickets in last 2 months
- Company wise tickets
- Ticket category wise active tickets
- Stage wise active tickets

## Usage

1. Go to **Helpdesk Dashboard > Layouts** and create a layout.
2. Add widgets and choose `Widget Type` (Counter/Chart).
3. Optionally set period, size, and extra domain.
4. Open **Helpdesk Dashboard > Dashboard** and drag widgets to reorder.

## Notes

- Depends on OCA `helpdesk_mgmt`.
- Default model used for metrics is `helpdesk.ticket`.
