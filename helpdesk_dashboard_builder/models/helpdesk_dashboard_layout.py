from odoo import api, fields, models


class HelpdeskDashboardLayout(models.Model):
    _name = "helpdesk.dashboard.layout"
    _description = "Helpdesk Dashboard Layout"
    _order = "name, id"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", string="User")
    is_global = fields.Boolean(default=False)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    widget_ids = fields.One2many("helpdesk.dashboard.widget", "layout_id", string="Widgets")

    _sql_constraints = [
        (
            "layout_scope_check",
            "CHECK(NOT(is_global) OR user_id IS NULL)",
            "Global layouts cannot be tied to a specific user.",
        )
    ]

    @api.model
    def get_current_layout(self):
        user_layout = self.search([
            ("user_id", "=", self.env.user.id),
            ("active", "=", True),
        ], limit=1)
        if user_layout:
            return user_layout
        return self.search([
            ("is_global", "=", True),
            ("company_id", "=", self.env.company.id),
            ("active", "=", True),
        ], limit=1)


class HelpdeskDashboardWidget(models.Model):
    _name = "helpdesk.dashboard.widget"
    _description = "Helpdesk Dashboard Widget"
    _order = "sequence, id"

    layout_id = fields.Many2one("helpdesk.dashboard.layout", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    widget_type = fields.Selection(
        [
            ("counter", "Counter"),
            ("chart", "Chart"),
            ("table", "Table"),
            ("activity", "Activity Feed"),
        ],
        required=True,
        default="counter",
    )
    model_name = fields.Char(default="helpdesk.ticket")
    domain = fields.Char(default="[]", help="Python domain string")
    group_by = fields.Char(help="Field name for grouping, e.g. team_id")
    measure_field = fields.Char(help="Optional measure field for charts")
    period = fields.Selection(
        [
            ("today", "Today"),
            ("7d", "Last 7 days"),
            ("30d", "Last 30 days"),
            ("90d", "Last 90 days"),
            ("all", "All time"),
        ],
        default="30d",
        required=True,
    )
    width = fields.Selection(
        [("full", "Full width"), ("half", "Half width"), ("third", "One third")],
        default="half",
        required=True,
    )
    height = fields.Integer(default=260)
    pos_x = fields.Integer(default=0)
    pos_y = fields.Integer(default=0)

    def _date_domain_for_period(self, period):
        if period == "all":
            return []
        days = {
            "today": 0,
            "7d": 7,
            "30d": 30,
            "90d": 90,
        }.get(period, 30)
        start = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        return [("create_date", ">=", start)]

    def _build_domain(self):
        self.ensure_one()
        base_domain = []
        if self.domain:
            base_domain = self.env["ir.filters"]._safe_eval(self.domain)
        return base_domain + self._date_domain_for_period(self.period)

    def get_widget_payload(self):
        self.ensure_one()
        model = self.env[self.model_name]
        domain = self._build_domain()
        payload = {
            "id": self.id,
            "name": self.name,
            "type": self.widget_type,
            "width": self.width,
            "height": self.height,
            "sequence": self.sequence,
            "group_by": self.group_by,
            "period": self.period,
        }

        if self.widget_type == "counter":
            payload["value"] = model.search_count(domain)
        elif self.widget_type == "table":
            records = model.search(domain, limit=10)
            payload["rows"] = records.read(["name", "create_date", "priority", "stage_id"])
        elif self.widget_type == "activity":
            messages = self.env["mail.message"].search(
                [("model", "=", self.model_name)] + domain,
                order="date desc",
                limit=10,
            )
            payload["items"] = messages.read(["author_id", "subject", "date"])
        else:  # chart
            group_field = self.group_by or "team_id"
            grouped = model.read_group(domain, ["id:count"], [group_field], lazy=False)
            payload["series"] = [
                {
                    "label": item.get(group_field) and item[group_field][1] or "Undefined",
                    "value": item.get("id_count", 0),
                }
                for item in grouped
            ]
        return payload


class HelpdeskDashboardController(models.AbstractModel):
    _name = "helpdesk.dashboard.controller"
    _description = "Helpdesk Dashboard Builder API"

    @api.model
    def get_dashboard_data(self):
        layout = self.env["helpdesk.dashboard.layout"].get_current_layout()
        if not layout:
            return {"layout": False, "widgets": []}
        widgets = layout.widget_ids.sorted("sequence")
        return {
            "layout": {
                "id": layout.id,
                "name": layout.name,
                "is_global": layout.is_global,
                "user_id": layout.user_id.id,
            },
            "widgets": [w.get_widget_payload() for w in widgets],
        }

    @api.model
    def save_widget_order(self, layout_id, ordered_widget_ids):
        layout = self.env["helpdesk.dashboard.layout"].browse(layout_id).exists()
        if not layout:
            return False
        for seq, widget_id in enumerate(ordered_widget_ids, start=1):
            widget = self.env["helpdesk.dashboard.widget"].browse(widget_id).exists()
            if widget and widget.layout_id.id == layout.id:
                widget.sequence = seq * 10
        return True
