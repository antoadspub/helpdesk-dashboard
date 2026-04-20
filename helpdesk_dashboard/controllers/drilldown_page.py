from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
import json


def _build_domain(period, team_filter, filter_open, adv_filters, group_by, label):
    """Build complete domain for drilldown."""
    domain = []
    if period and str(period) != '0':
        domain.append(('create_date', '>=', (datetime.now() - timedelta(days=int(period)*30)).strftime('%Y-%m-%d')))
    if team_filter:
        domain.append(('team_id', '=', int(team_filter)))
    if filter_open:
        domain.append(('closed', '=', False))

    # Group-by segment filter
    if group_by == 'user':
        if label == 'Unassigned':
            domain.append(('user_id', '=', False))
        else:
            u = request.env['res.users'].search([('name','=',label)], limit=1)
            domain.append(('user_id', '=', u.id if u else 0))
    elif group_by == 'team':
        if label == 'No Team':
            domain.append(('team_id', '=', False))
        else:
            t = request.env['helpdesk.ticket.team'].search([('name','=',label)], limit=1)
            domain.append(('team_id', '=', t.id if t else 0))
    elif group_by == 'type':
        if label == 'No Type':
            domain.append(('type_id', '=', False))
        else:
            t = request.env['helpdesk.ticket.type'].search([('name','=',label)], limit=1)
            domain.append(('type_id', '=', t.id if t else 0))
    elif group_by == 'stage':
        s = request.env['helpdesk.ticket.stage'].search([('name','=',label)], limit=1)
        domain.append(('stage_id', '=', s.id if s else 0))
    elif group_by == 'priority':
        rmap = {'Low':'0','Medium':'1','High':'2','Very High':'3'}
        domain.append(('priority', '=', rmap.get(label, '1')))
    elif group_by == 'category':
        if label == 'No Category':
            domain.append(('category_id', '=', False))
        else:
            c = request.env['helpdesk.ticket.category'].search([('name','=',label)], limit=1)
            domain.append(('category_id', '=', c.id if c else 0))
    elif group_by == 'channel':
        if label == 'No Channel':
            domain.append(('channel_id', '=', False))
        else:
            ch = request.env['helpdesk.ticket.channel'].search([('name','=',label)], limit=1)
            domain.append(('channel_id', '=', ch.id if ch else 0))
    elif group_by == 'date':
        try:
            d = datetime.strptime(label, '%d/%m/%y')
            domain += [('create_date', '>=', d.strftime('%Y-%m-%d')),
                       ('create_date', '<', (d + timedelta(days=1)).strftime('%Y-%m-%d'))]
        except Exception:
            pass
    elif group_by == 'hour':
        domain.append(('create_date', '!=', False))

    return domain
