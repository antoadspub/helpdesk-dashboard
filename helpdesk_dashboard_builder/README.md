# Helpdesk Dashboard Builder (Odoo 18 CE)

This module adds a configurable Helpdesk dashboard for managers with drag-and-drop layout control.

## Required widget metrics

Each metric can be shown as **Counter** or **Chart**:

- Assigned engineer active tickets
- Assigned engineer closed tickets in last 2 months
- Company wise tickets
- Ticket category wise active tickets
- Stage wise active tickets

## How to configure these requirements

1. Go to **Helpdesk Dashboard > Layouts** and create/open a layout.
2. Click **Generate Required Widgets** (creates the five required widgets automatically).
3. In the Widgets list, set **Widget Type** as `Counter` or `Chart` per metric.
4. In **Metric**, choose one of the required metrics listed above.
5. Optionally set period, width/height, and extra domain.
6. Open **Helpdesk Dashboard > Dashboard** and drag widgets to reorder.

## Notes

- Depends on OCA `helpdesk_mgmt`.
- Default model used for metrics is `helpdesk.ticket`.
