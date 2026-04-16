import json
from odoo import fields, models, api


class HdDashboardLayout(models.Model):
    _name = 'hd.dashboard.layout'
    _description = 'Helpdesk Dashboard Layout'

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade')
    is_default = fields.Boolean(string='Shared default layout', default=False)
    widget_ids = fields.One2many('hd.dashboard.widget', 'layout_id', string='Widgets')

    @api.model
    def get_layout(self, user_id=None):
        """Get layout for current user, fallback to default."""
        uid = user_id or self.env.uid
        layout = self.search([('user_id', '=', uid)], limit=1)
        if not layout:
            layout = self.search([('is_default', '=', True)], limit=1)
        if not layout:
            layout = self._create_default_layout()
        return layout

    def _create_default_layout(self):
        """Create a sensible default layout."""
        layout = self.create({'is_default': True})
        defaults = [
            {'widget_type': 'counter', 'title': 'Open Tickets',    'metric': 'open',       'color': 'blue',   'size': 'small', 'position': 1},
            {'widget_type': 'counter', 'title': 'Assigned',         'metric': 'assigned',   'color': 'amber',  'size': 'small', 'position': 2},
            {'widget_type': 'counter', 'title': 'Resolved',         'metric': 'resolved',   'color': 'green',  'size': 'small', 'position': 3},
            {'widget_type': 'counter', 'title': 'Unassigned',       'metric': 'unassigned', 'color': 'purple', 'size': 'small', 'position': 4},
            {'widget_type': 'bar',     'title': 'Tickets by Tech (Ongoing)', 'group_by': 'user',   'period': '1', 'filter_open': True,  'size': 'half',  'position': 5},
            {'widget_type': 'bar',     'title': 'Tickets by Tech (Period)',  'group_by': 'user',   'period': '1', 'filter_open': False, 'size': 'half',  'position': 6},
            {'widget_type': 'bar',     'title': 'By Hour of Day',   'group_by': 'hour',   'period': '1', 'size': 'half',  'position': 7},
            {'widget_type': 'bar',     'title': 'By Date Opened',   'group_by': 'date',   'period': '1', 'size': 'half',  'position': 8},
            {'widget_type': 'donut',   'title': 'By Status',        'group_by': 'stage',  'period': '1', 'size': 'third', 'position': 9},
            {'widget_type': 'donut',   'title': 'By Team',          'group_by': 'team',   'period': '1', 'size': 'third', 'position': 10},
            {'widget_type': 'bar',     'title': 'By Request Type',  'group_by': 'type',   'period': '1', 'size': 'third', 'position': 11},
            {'widget_type': 'leaderboard', 'title': 'Leaderboard',  'metric': 'closed',   'period': '1', 'size': 'half',  'position': 12},
            {'widget_type': 'activity','title': 'Recent Activity',                         'period': '1', 'size': 'half',  'position': 13},
        ]
        for d in defaults:
            d['layout_id'] = layout.id
            self.env['hd.dashboard.widget'].create(d)
        return layout


class HdDashboardWidget(models.Model):
    _name = 'hd.dashboard.widget'
    _description = 'Helpdesk Dashboard Widget'
    _order = 'position, id'

    layout_id = fields.Many2one('hd.dashboard.layout', ondelete='cascade', required=True)
    widget_type = fields.Selection([
        ('counter',     'Counter Card'),
        ('bar',         'Bar Chart'),
        ('donut',       'Donut Chart'),
        ('line',        'Line / Trend Chart'),
        ('leaderboard', 'Leaderboard'),
        ('activity',    'Activity Feed'),
        ('table',       'Ticket Table'),
    ], string='Widget Type', required=True, default='counter')

    title = fields.Char(required=True, default='Widget')
    position = fields.Integer(default=99)
    size = fields.Selection([
        ('small', 'Small (1/4)'),
        ('third', 'Medium (1/3)'),
        ('half',  'Half (1/2)'),
        ('full',  'Full width'),
    ], default='half')

    color = fields.Selection([
        ('blue',   'Blue'),
        ('amber',  'Amber'),
        ('green',  'Green'),
        ('purple', 'Purple'),
        ('teal',   'Teal'),
        ('coral',  'Coral'),
    ], default='blue')

    # Data options
    group_by = fields.Selection([
        ('user',     'Assigned Tech'),
        ('team',     'Team'),
        ('type',     'Ticket Type'),
        ('stage',    'Stage / Status'),
        ('priority', 'Priority'),
        ('category', 'Category'),
        ('channel',  'Channel'),
        ('date',     'Date Opened'),
        ('hour',     'Hour of Day'),
    ], string='Group By')

    metric = fields.Selection([
        ('open',       'Open tickets'),
        ('assigned',   'Assigned tickets'),
        ('resolved',   'Resolved tickets'),
        ('unassigned', 'Unassigned tickets'),
        ('total',      'Total tickets'),
        ('closed',     'Closed (leaderboard)'),
        ('avg_time',   'Avg resolution time'),
    ], string='Metric', default='open')

    period = fields.Selection([
        ('1',  'Last 1 month'),
        ('3',  'Last 3 months'),
        ('6',  'Last 6 months'),
        ('12', 'Last 12 months'),
        ('0',  'All time'),
    ], default='1', string='Period')

    team_filter = fields.Many2one('helpdesk.ticket.team', string='Filter by Team')
    filter_open = fields.Boolean(string='Only open tickets', default=False)
    limit = fields.Integer(string='Row limit', default=10)

    def to_dict(self):
        self.ensure_one()
        return {
            'id': self.id,
            'widget_type': self.widget_type,
            'title': self.title,
            'position': self.position,
            'size': self.size,
            'color': self.color,
            'group_by': self.group_by,
            'metric': self.metric,
            'period': self.period,
            'team_filter': self.team_filter.id if self.team_filter else False,
            'team_filter_name': self.team_filter.name if self.team_filter else '',
            'filter_open': self.filter_open,
            'limit': self.limit,
        }
