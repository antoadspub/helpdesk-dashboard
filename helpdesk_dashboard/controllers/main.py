import json
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from collections import defaultdict


def _check_access():
    u = request.env.user
    return u.has_group('helpdesk_mgmt.group_helpdesk_manager') or \
           u.has_group('helpdesk_mgmt.group_helpdesk_user')


def _build_domain(period, team_filter, filter_open, adv_filters):
    domain = []
    # Period
    if period and str(period) != '0':
        domain.append(('create_date', '>=', datetime.now() - timedelta(days=int(period)*30)))
    # Team
    if team_filter:
        domain.append(('team_id', '=', int(team_filter)))
    # Open only
    if filter_open:
        domain.append(('closed', '=', False))
    # Advanced filters
    if adv_filters:
        and_conds, or_conds = [], []
        for f in adv_filters:
            cond = _single_cond(f)
            if cond:
                (or_conds if f.get('logic') == 'OR' else and_conds).append(cond)
        domain.extend(and_conds)
        if or_conds:
            or_domain = []
            for i, c in enumerate(or_conds):
                if i > 0:
                    or_domain.insert(0, '|')
                or_domain.append(c)
            domain.extend(or_domain)
    return domain


def _single_cond(f):
    field_map = {
        'stage':    'stage_id.name',
        'user':     'user_id.name',
        'team':     'team_id.name',
        'type':     'type_id.name',
        'category': 'category_id.name',
        'priority': 'priority',
        'closed':   'closed',
    }
    field = f.get('field', '')
    op    = f.get('op', '=')
    value = f.get('value', '')
    if not field or value == '':
        return None
    odoo_field = field_map.get(field, field)
    if field == 'closed':
        value = (value == 'true')
    return (odoo_field, op, value)


class HelpdeskDashboard(http.Controller):

    @http.route('/hd/dashboard/layout/get', type='json', auth='user')
    def layout_get(self, **kw):
        if not _check_access():
            return {'error': 'Access denied'}
        layout = request.env['hd.dashboard.layout'].get_layout()
        teams      = request.env['helpdesk.ticket.team'].search([])
        stages     = request.env['helpdesk.ticket.stage'].search([])
        users      = request.env['res.users'].search([('share','=',False),('active','=',True)])
        categories = request.env['helpdesk.ticket.category'].search([])
        types = []
        if 'helpdesk.ticket.type' in request.env:
            types = request.env['helpdesk.ticket.type'].search([])
        return {
            'layout_id':  layout.id,
            'is_default': layout.is_default,
            'is_manager': request.env.user.has_group('helpdesk_mgmt.group_helpdesk_manager'),
            'widgets':    [w.to_dict() for w in layout.widget_ids],
            'teams':      [{'id':t.id,'name':t.name} for t in teams],
            'stages':     [{'id':s.id,'name':s.name,'closed':s.closed} for s in stages],
            'users':      [{'id':u.id,'name':u.name} for u in users],
            'types':      [{'id':t.id,'name':t.name} for t in types],
            'categories': [{'id':c.id,'name':c.name} for c in categories],
        }

    @http.route('/hd/dashboard/layout/save', type='json', auth='user')
    def layout_save(self, widgets, save_as_default=False, **kw):
        if not _check_access():
            return {'error': 'Access denied'}
        Layout = request.env['hd.dashboard.layout']
        Widget = request.env['hd.dashboard.widget']
        if save_as_default:
            if not request.env.user.has_group('helpdesk_mgmt.group_helpdesk_manager'):
                return {'error': 'Only managers can save shared layout'}
            layout = Layout.search([('is_default','=',True)], limit=1)
            if not layout:
                layout = Layout.create({'is_default': True})
            else:
                layout.widget_ids.unlink()
        else:
            layout = Layout.search([('user_id','=',request.env.uid)], limit=1)
            if not layout:
                layout = Layout.create({'user_id': request.env.uid})
            else:
                layout.widget_ids.unlink()
        for w in widgets:
            adv = w.get('adv_filters') or []
            Widget.create({
                'layout_id':   layout.id,
                'widget_type': w.get('widget_type','counter'),
                'title':       w.get('title','Widget'),
                'position':    w.get('position',99),
                'size':        w.get('size','half'),
                'color':       w.get('color','blue'),
                'group_by':    w.get('group_by') or False,
                'metric':      w.get('metric') or 'open',
                'period':      w.get('period','1'),
                'team_filter': w.get('team_filter') or False,
                'filter_open': w.get('filter_open',False),
                'limit':       w.get('limit',10),
                'adv_filters': json.dumps(adv),
            })
        return {'success': True, 'layout_id': layout.id}

    @http.route('/hd/dashboard/layout/reset', type='json', auth='user')
    def layout_reset(self, **kw):
        layout = request.env['hd.dashboard.layout'].search([('user_id','=',request.env.uid)], limit=1)
        if layout:
            layout.unlink()
        return {'success': True}

    @http.route('/hd/dashboard/widget/data', type='json', auth='user')
    def widget_data(self, widget, **kw):
        if not _check_access():
            return {'error': 'Access denied'}
        wtype       = widget.get('widget_type')
        period      = widget.get('period','1')
        team_fid    = widget.get('team_filter')
        filter_open = widget.get('filter_open',False)
        adv_filters = widget.get('adv_filters') or []
        group_by    = widget.get('group_by')
        metric      = widget.get('metric','open')
        limit       = int(widget.get('limit',10))
        Ticket      = request.env['helpdesk.ticket']
        domain      = _build_domain(period, team_fid, filter_open, adv_filters)
        if wtype == 'counter':
            return self._counter(Ticket, metric, domain)
        elif wtype in ('bar','donut','line'):
            return self._chart(Ticket, group_by, domain, limit)
        elif wtype == 'leaderboard':
            return self._leaderboard(Ticket, metric, domain, limit)
        elif wtype == 'activity':
            return self._activity(Ticket, domain, limit)
        elif wtype == 'table':
            return self._table(Ticket, domain, limit)
        return {}

    @http.route('/hd/dashboard/widget/drilldown', type='json', auth='user')
    def widget_drilldown(self, group_by, label, period, team_filter,
                         filter_open, adv_filters=None, **kw):
        if not _check_access():
            return {'error': 'Access denied'}
        Ticket = request.env['helpdesk.ticket']
        domain = _build_domain(period, team_filter, filter_open, adv_filters or [])
        if group_by == 'user':
            if label == 'Unassigned':
                domain.append(('user_id','=',False))
            else:
                u = request.env['res.users'].search([('name','=',label)], limit=1)
                domain.append(('user_id','=',u.id if u else 0))
        elif group_by == 'team':
            if label == 'No Team':
                domain.append(('team_id','=',False))
            else:
                t = request.env['helpdesk.ticket.team'].search([('name','=',label)], limit=1)
                domain.append(('team_id','=',t.id if t else 0))
        elif group_by == 'type':
            if label == 'No Type':
                domain.append(('type_id','=',False))
            else:
                t = request.env['helpdesk.ticket.type'].search([('name','=',label)], limit=1)
                domain.append(('type_id','=',t.id if t else 0))
        elif group_by == 'stage':
            s = request.env['helpdesk.ticket.stage'].search([('name','=',label)], limit=1)
            domain.append(('stage_id','=',s.id if s else 0))
        elif group_by == 'priority':
            rmap = {'Low':'0','Medium':'1','High':'2','Very High':'3'}
            domain.append(('priority','=',rmap.get(label,'1')))
        elif group_by == 'category':
            if label == 'No Category':
                domain.append(('category_id','=',False))
            else:
                c = request.env['helpdesk.ticket.category'].search([('name','=',label)], limit=1)
                domain.append(('category_id','=',c.id if c else 0))
        elif group_by == 'channel':
            if label == 'No Channel':
                domain.append(('channel_id','=',False))
            else:
                ch = request.env['helpdesk.ticket.channel'].search([('name','=',label)], limit=1)
                domain.append(('channel_id','=',ch.id if ch else 0))
        elif group_by == 'date':
            try:
                d = datetime.strptime(label, '%d/%m/%y')
                domain += [('create_date','>=',d.strftime('%Y-%m-%d')),
                           ('create_date','<',(d+timedelta(days=1)).strftime('%Y-%m-%d'))]
            except Exception:
                pass
        tickets = Ticket.search(domain, limit=100)
        rows = [{'id':t.id,'number':t.number,'name':t.name,
                 'stage':t.stage_id.name if t.stage_id else '',
                 'closed':t.stage_id.closed if t.stage_id else False,
                 'user':t.user_id.name if t.user_id else 'Unassigned',
                 'team':t.team_id.name if t.team_id else '',
                 'priority':t.priority,
                 'date':t.create_date.strftime('%d/%m/%y') if t.create_date else ''}
                for t in tickets]
        return {'rows': rows, 'label': label, 'total': len(rows)}

    def _counter(self, Ticket, metric, domain):
        if metric == 'open':
            count = Ticket.search_count([('closed','=',False)])
            sub   = 'Not closed'
        elif metric == 'assigned':
            count = Ticket.search_count([('closed','=',False),('user_id','!=',False)])
            sub   = 'Has assignee'
        elif metric == 'unassigned':
            count = Ticket.search_count([('closed','=',False),('user_id','=',False)])
            sub   = 'Needs assignment'
        elif metric == 'resolved':
            tickets = Ticket.search(domain)
            count   = len(tickets.filtered(lambda t: t.stage_id.closed))
            sub     = 'Closed this period'
        elif metric == 'total':
            count = Ticket.search_count(domain)
            sub   = 'This period'
        elif metric == 'avg_time':
            tickets = Ticket.search(domain + [('closed_date','!=',False),('assigned_date','!=',False)])
            times = [(t.closed_date-t.assigned_date).total_seconds()/3600
                     for t in tickets if t.closed_date and t.assigned_date]
            count = round(sum(times)/len(times),1) if times else 0
            sub   = 'Hours avg'
        else:
            count = Ticket.search_count(domain)
            sub   = ''
        stage_counts = {}
        for t in Ticket.search([('closed','=',False)]):
            sn = t.stage_id.name if t.stage_id else 'No Stage'
            stage_counts[sn] = stage_counts.get(sn, 0) + 1
        return {'value': count, 'sub': sub, 'stage_counts': stage_counts}

    def _chart(self, Ticket, group_by, domain, limit):
        if not group_by:
            return {'labels':[], 'data':[]}
        tickets = Ticket.search(domain)
        counts  = defaultdict(int)
        if group_by == 'user':
            for t in tickets: counts[t.user_id.name if t.user_id else 'Unassigned'] += 1
        elif group_by == 'team':
            for t in tickets: counts[t.team_id.name if t.team_id else 'No Team'] += 1
        elif group_by == 'type':
            for t in tickets:
                counts[(t.type_id.name if hasattr(t,'type_id') and t.type_id else 'No Type')] += 1
        elif group_by == 'stage':
            for t in tickets: counts[t.stage_id.name if t.stage_id else 'No Stage'] += 1
        elif group_by == 'priority':
            pm = {'0':'Low','1':'Medium','2':'High','3':'Very High'}
            for t in tickets: counts[pm.get(t.priority, t.priority)] += 1
        elif group_by == 'category':
            for t in tickets: counts[t.category_id.name if t.category_id else 'No Category'] += 1
        elif group_by == 'channel':
            for t in tickets: counts[t.channel_id.name if t.channel_id else 'No Channel'] += 1
        elif group_by == 'date':
            for t in tickets:
                if t.create_date: counts[t.create_date.strftime('%d/%m/%y')] += 1
            sc = sorted(counts.items(), key=lambda x: datetime.strptime(x[0],'%d/%m/%y'))[-limit:]
            return {'labels':[x[0] for x in sc],'data':[x[1] for x in sc]}
        elif group_by == 'hour':
            for t in tickets:
                if t.create_date: counts[f"{t.create_date.hour:02d}:00"] += 1
            sc = sorted(counts.items())
            return {'labels':[x[0] for x in sc],'data':[x[1] for x in sc]}
        sc = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return {'labels':[x[0] for x in sc],'data':[x[1] for x in sc]}

    def _leaderboard(self, Ticket, metric, domain, limit):
        if metric == 'closed':
            d = list(domain) + [('closed','=',True)]
            tickets = Ticket.search(d)
            counts  = defaultdict(int)
            for t in tickets:
                if t.user_id: counts[t.user_id.name] += 1
            rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return {'rows':[{'name':r[0],'value':r[1],'label':'closed'} for r in rows]}
        elif metric == 'avg_time':
            d = list(domain) + [('closed_date','!=',False),('assigned_date','!=',False)]
            tickets = Ticket.search(d)
            times = defaultdict(list)
            for t in tickets:
                if t.user_id and t.closed_date and t.assigned_date:
                    times[t.user_id.name].append((t.closed_date-t.assigned_date).total_seconds()/3600)
            rows = [(n,round(sum(h)/len(h),1)) for n,h in times.items()]
            rows.sort(key=lambda x: x[1])
            return {'rows':[{'name':r[0],'value':r[1],'label':'hrs'} for r in rows[:limit]]}
        else:
            d = list(domain) + [('closed','=',False)]
            tickets = Ticket.search(d)
            counts  = defaultdict(int)
            for t in tickets:
                if t.user_id: counts[t.user_id.name] += 1
            rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return {'rows':[{'name':r[0],'value':r[1],'label':'open'} for r in rows]}

    def _activity(self, Ticket, domain, limit):
        tickets = Ticket.search(domain, order='write_date desc', limit=limit)
        return {'rows':[{'id':t.id,'number':t.number,'name':t.name,
            'stage':t.stage_id.name if t.stage_id else '',
            'closed':t.stage_id.closed if t.stage_id else False,
            'unattended':t.stage_id.unattended if t.stage_id else False,
            'user':t.user_id.name if t.user_id else 'Unassigned',
            'team':t.team_id.name if t.team_id else '',
            'priority':t.priority,
            'date':t.write_date.strftime('%d/%m/%y %H:%M') if t.write_date else ''}
            for t in tickets]}

    def _table(self, Ticket, domain, limit):
        tickets = Ticket.search(domain, order='create_date desc', limit=limit)
        return {'rows':[{'id':t.id,'number':t.number,'name':t.name,
            'stage':t.stage_id.name if t.stage_id else '',
            'closed':t.stage_id.closed if t.stage_id else False,
            'user':t.user_id.name if t.user_id else '',
            'team':t.team_id.name if t.team_id else '',
            'priority':t.priority,
            'type':t.type_id.name if hasattr(t,'type_id') and t.type_id else '',
            'date':t.create_date.strftime('%d/%m/%y') if t.create_date else ''}
            for t in tickets]}
