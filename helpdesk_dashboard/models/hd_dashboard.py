import json
from odoo import fields, models, api


class HdDashboardLayout(models.Model):
    _name = 'hd.dashboard.layout'
    _description = 'Helpdesk Dashboard Layout'

    user_id    = fields.Many2one('res.users', string='User', ondelete='cascade')
    is_default = fields.Boolean(string='Shared default layout', default=False)
    widget_ids = fields.One2many('hd.dashboard.widget', 'layout_id', string='Widgets')

    @api.model
    def get_layout(self):
        uid = self.env.uid
        layout = self.search([('user_id', '=', uid)], limit=1)
        if not layout:
            layout = self.search([('is_default', '=', True)], limit=1)
        if not layout:
            layout = self._create_default_layout()
        return layout

    def _create_default_layout(self):
        layout = self.create({'is_default': True})
        defaults = [
            {'widget_type':'counter','title':'Open Tickets',         'metric':'open',       'color':'blue',   'size':'small','period':'1','position':1},
            {'widget_type':'counter','title':'Assigned',              'metric':'assigned',   'color':'amber',  'size':'small','period':'1','position':2},
            {'widget_type':'counter','title':'Resolved',              'metric':'resolved',   'color':'green',  'size':'small','period':'1','position':3},
            {'widget_type':'counter','title':'Unassigned',            'metric':'unassigned', 'color':'purple', 'size':'small','period':'1','position':4},
            {'widget_type':'bar',   'title':'Tickets by Tech (Open)', 'group_by':'user',   'period':'1','filter_open':True, 'size':'half','position':5},
            {'widget_type':'bar',   'title':'Tickets by Tech (Period)','group_by':'user',  'period':'1','filter_open':False,'size':'half','position':6},
            {'widget_type':'bar',   'title':'By Hour of Day',         'group_by':'hour',   'period':'1','size':'half','position':7},
            {'widget_type':'bar',   'title':'By Date Opened',         'group_by':'date',   'period':'1','size':'half','position':8},
            {'widget_type':'donut', 'title':'By Stage',               'group_by':'stage',  'period':'1','size':'third','position':9},
            {'widget_type':'donut', 'title':'By Team',                'group_by':'team',   'period':'1','size':'third','position':10},
            {'widget_type':'bar',   'title':'By Request Type',        'group_by':'type',   'period':'1','size':'third','position':11},
            {'widget_type':'leaderboard','title':'Leaderboard',       'metric':'closed',   'period':'1','size':'half','position':12},
            {'widget_type':'activity',  'title':'Recent Activity',                         'period':'1','size':'half','position':13},
        ]
        for d in defaults:
            d['layout_id'] = layout.id
            self.env['hd.dashboard.widget'].create(d)
        return layout


class HdDashboardWidget(models.Model):
    _name = 'hd.dashboard.widget'
    _description = 'Helpdesk Dashboard Widget'
    _order = 'position, id'

    layout_id   = fields.Many2one('hd.dashboard.layout', ondelete='cascade', required=True)
    widget_type = fields.Selection([
        ('counter','Counter Card'), ('bar','Bar Chart'), ('donut','Donut Chart'),
        ('line','Trend Chart'), ('leaderboard','Leaderboard'),
        ('activity','Activity Feed'), ('table','Ticket Table'),
    ], required=True, default='counter')
    title       = fields.Char(required=True, default='Widget')
    position    = fields.Integer(default=99)
    size        = fields.Selection([('small','Small'),('third','Medium'),('half','Half'),('full','Full')], default='half')
    color       = fields.Selection([('blue','Blue'),('amber','Amber'),('green','Green'),('purple','Purple'),('teal','Teal'),('coral','Coral')], default='blue')
    group_by    = fields.Selection([
        ('user','Assigned Tech'),('team','Team'),('type','Ticket Type'),
        ('stage','Stage'),('priority','Priority'),('category','Category'),
        ('channel','Channel'),('date','Date Opened'),('hour','Hour of Day'),
    ])
    metric      = fields.Selection([
        ('open','Open tickets'),('assigned','Assigned'),('unassigned','Unassigned'),
        ('resolved','Resolved'),('total','Total'),('closed','Closed'),('avg_time','Avg time'),
    ], default='open')
    period      = fields.Selection([('1','1 month'),('3','3 months'),('6','6 months'),('12','12 months'),('0','All time')], default='1')
    team_filter = fields.Many2one('helpdesk.ticket.team')
    filter_open = fields.Boolean(default=False)
    limit       = fields.Integer(default=10)
    # Per-widget advanced filters stored as JSON array
    adv_filters = fields.Text(default='[]')

    def to_dict(self):
        self.ensure_one()
        try:
            adv = json.loads(self.adv_filters or '[]')
        except Exception:
            adv = []
        return {
            'id': self.id, 'widget_type': self.widget_type,
            'title': self.title, 'position': self.position,
            'size': self.size, 'color': self.color,
            'group_by': self.group_by, 'metric': self.metric,
            'period': self.period,
            'team_filter': self.team_filter.id if self.team_filter else False,
            'team_filter_name': self.team_filter.name if self.team_filter else '',
            'filter_open': self.filter_open,
            'limit': self.limit,
            'adv_filters': adv,
        }
