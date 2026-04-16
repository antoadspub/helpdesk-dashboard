from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from collections import defaultdict


def _check_access():
    user = request.env.user
    return (user.has_group('helpdesk_mgmt.group_helpdesk_manager') or
            user.has_group('helpdesk_mgmt.group_helpdesk_user'))


def _date_domain(period):
    if period and period != '0':
        date_from = datetime.now() - timedelta(days=int(period) * 30)
        return [('create_date', '>=', date_from)]
    return []


class HelpdeskDashboardV2(http.Controller):

    # ─── Layout endpoints ────────────────────────────────────────────

    @http.route('/hd/dashboard/layout/get', type='json', auth='user')
    def layout_get(self, **kw):
        if not _check_access():
            return {'error': 'Access denied'}
        layout = request.env['hd.dashboard.layout'].get_layout()
        teams = request.env['helpdesk.ticket.team'].search([])
        return {
            'layout_id': layout.id,
            'is_default': layout.is_default,
            'is_manager': request.env.user.has_group('helpdesk_mgmt.group_helpdesk_manager'),
            'widgets': [w.to_dict() for w in layout.widget_ids],
            'teams': [{'id': t.id, 'name': t.name} for t in teams],
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
            # Update or create default layout
            layout = Layout.search([('is_default', '=', True)], limit=1)
            if not layout:
                layout = Layout.create({'is_default': True})
            else:
                layout.widget_ids.unlink()
        else:
            # Personal layout
            layout = Layout.search([('user_id', '=', request.env.uid)], limit=1)
            if not layout:
                layout = Layout.create({'user_id': request.env.uid})
            else:
                layout.widget_ids.unlink()

        for w in widgets:
            Widget.create({
                'layout_id': layout.id,
                'widget_type': w.get('widget_type', 'counter'),
                'title': w.get('title', 'Widget'),
                'position': w.get('position', 99),
                'size': w.get('size', 'half'),
                'color': w.get('color', 'blue'),
                'group_by': w.get('group_by') or False,
                'metric': w.get('metric') or 'open',
                'period': w.get('period', '1'),
                'team_filter': w.get('team_filter') or False,
                'filter_open': w.get('filter_open', False),
                'limit': w.get('limit', 10),
            })
        return {'success': True, 'layout_id': layout.id}

    @http.route('/hd/dashboard/layout/reset', type='json', auth='user')
    def layout_reset(self, **kw):
        """Delete personal layout so user falls back to shared default."""
        layout = request.env['hd.dashboard.layout'].search(
            [('user_id', '=', request.env.uid)], limit=1)
        if layout:
            layout.unlink()
        return {'success': True}

    # ─── Widget data endpoint ────────────────────────────────────────

    @http.route('/hd/dashboard/widget/data', type='json', auth='user')
    def widget_data(self, widget, **kw):
        if not _check_access():
            return {'error': 'Access denied'}

        wtype    = widget.get('widget_type')
        period   = widget.get('period', '1')
        group_by = widget.get('group_by')
        metric   = widget.get('metric', 'open')
        team_fid = widget.get('team_filter')
        filter_open = widget.get('filter_open', False)
        limit    = int(widget.get('limit', 10))

        Ticket = request.env['helpdesk.ticket']
        base_domain = _date_domain(period)
        if team_fid:
            base_domain.append(('team_id', '=', int(team_fid)))
        if filter_open:
            base_domain.append(('closed', '=', False))

        if wtype == 'counter':
            return self._counter_data(Ticket, metric, base_domain)
        elif wtype in ('bar', 'donut', 'line'):
            return self._chart_data(Ticket, group_by, base_domain, wtype, limit)
        elif wtype == 'leaderboard':
            return self._leaderboard_data(Ticket, metric, period, team_fid, limit)
        elif wtype == 'activity':
            return self._activity_data(Ticket, base_domain, limit)
        elif wtype == 'table':
            return self._table_data(Ticket, base_domain, limit)
        return {}

    def _counter_data(self, Ticket, metric, base_domain):
        open_domain   = [('closed', '=', False)]
        period_domain = base_domain

        if metric == 'open':
            count = Ticket.search_count([('closed', '=', False)])
            sub   = 'Not closed'
        elif metric == 'assigned':
            count = Ticket.search_count([('closed', '=', False), ('user_id', '!=', False)])
            sub   = 'In progress'
        elif metric == 'unassigned':
            count = Ticket.search_count([('closed', '=', False), ('user_id', '=', False)])
            sub   = 'Needs assignment'
        elif metric == 'resolved':
            tickets = Ticket.search(period_domain)
            count   = len(tickets.filtered(lambda t: t.stage_id.closed))
            sub     = 'This period'
        elif metric == 'total':
            count = Ticket.search_count(period_domain)
            sub   = 'This period'
        elif metric == 'avg_time':
            tickets = Ticket.search(period_domain + [('closed_date', '!=', False), ('assigned_date', '!=', False)])
            if tickets:
                times = [(t.closed_date - t.assigned_date).total_seconds() / 3600
                         for t in tickets if t.closed_date and t.assigned_date]
                count = round(sum(times) / len(times), 1) if times else 0
            else:
                count = 0
            sub = 'Hours avg'
        else:
            count = Ticket.search_count(period_domain)
            sub   = ''
        return {'value': count, 'sub': sub}

    def _chart_data(self, Ticket, group_by, base_domain, wtype, limit):
        tickets = Ticket.search(base_domain)
        counts  = defaultdict(int)

        if group_by == 'user':
            for t in tickets:
                label = t.user_id.name if t.user_id else 'Unassigned'
                counts[label] += 1
        elif group_by == 'team':
            for t in tickets:
                label = t.team_id.name if t.team_id else 'No Team'
                counts[label] += 1
        elif group_by == 'type':
            for t in tickets:
                label = t.type_id.name if hasattr(t, 'type_id') and t.type_id else 'No Type'
                counts[label] += 1
        elif group_by == 'stage':
            for t in tickets:
                label = t.stage_id.name if t.stage_id else 'No Stage'
                counts[label] += 1
        elif group_by == 'priority':
            pmap = {'0': 'Low', '1': 'Medium', '2': 'High', '3': 'Very High'}
            for t in tickets:
                counts[pmap.get(t.priority, t.priority)] += 1
        elif group_by == 'category':
            for t in tickets:
                label = t.category_id.name if t.category_id else 'No Category'
                counts[label] += 1
        elif group_by == 'channel':
            for t in tickets:
                label = t.channel_id.name if t.channel_id else 'No Channel'
                counts[label] += 1
        elif group_by == 'date':
            for t in tickets:
                if t.create_date:
                    counts[t.create_date.strftime('%d/%m/%y')] += 1
            # Sort by date
            sorted_counts = sorted(counts.items(),
                key=lambda x: datetime.strptime(x[0], '%d/%m/%y'))[-limit:]
            return {
                'labels': [x[0] for x in sorted_counts],
                'data':   [x[1] for x in sorted_counts],
            }
        elif group_by == 'hour':
            for t in tickets:
                if t.create_date:
                    counts[f"{t.create_date.hour:02d}:00"] += 1
            sorted_counts = sorted(counts.items())
            return {
                'labels': [x[0] for x in sorted_counts],
                'data':   [x[1] for x in sorted_counts],
            }

        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return {
            'labels': [x[0] for x in sorted_counts],
            'data':   [x[1] for x in sorted_counts],
        }

    def _leaderboard_data(self, Ticket, metric, period, team_fid, limit):
        domain = _date_domain(period)
        if team_fid:
            domain.append(('team_id', '=', int(team_fid)))

        if metric == 'closed':
            domain.append(('closed', '=', True))
            tickets = Ticket.search(domain)
            counts  = defaultdict(int)
            for t in tickets:
                if t.user_id:
                    counts[t.user_id.name] += 1
            rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return {'rows': [{'name': r[0], 'value': r[1], 'label': 'closed'} for r in rows]}

        elif metric == 'avg_time':
            tickets = Ticket.search(domain + [
                ('closed_date', '!=', False), ('assigned_date', '!=', False)])
            times = defaultdict(list)
            for t in tickets:
                if t.user_id and t.closed_date and t.assigned_date:
                    hours = (t.closed_date - t.assigned_date).total_seconds() / 3600
                    times[t.user_id.name].append(hours)
            rows = [(name, round(sum(hrs)/len(hrs), 1))
                    for name, hrs in times.items()]
            rows.sort(key=lambda x: x[1])
            return {'rows': [{'name': r[0], 'value': r[1], 'label': 'hrs avg'} for r in rows[:limit]]}

        else:  # open
            domain.append(('closed', '=', False))
            tickets = Ticket.search(domain)
            counts  = defaultdict(int)
            for t in tickets:
                if t.user_id:
                    counts[t.user_id.name] += 1
            rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return {'rows': [{'name': r[0], 'value': r[1], 'label': 'open'} for r in rows]}

    def _activity_data(self, Ticket, base_domain, limit):
        tickets = Ticket.search(base_domain, order='write_date desc', limit=limit)
        rows = []
        for t in tickets:
            rows.append({
                'id':      t.id,
                'number':  t.number,
                'name':    t.name,
                'stage':   t.stage_id.name if t.stage_id else '',
                'closed':  t.stage_id.closed if t.stage_id else False,
                'user':    t.user_id.name if t.user_id else 'Unassigned',
                'partner': t.partner_id.name if t.partner_id else '',
                'team':    t.team_id.name if t.team_id else '',
                'priority': t.priority,
                'date':    t.write_date.strftime('%d/%m/%y %H:%M') if t.write_date else '',
            })
        return {'rows': rows}

    def _table_data(self, Ticket, base_domain, limit):
        tickets = Ticket.search(base_domain, order='create_date desc', limit=limit)
        rows = []
        for t in tickets:
            rows.append({
                'id':       t.id,
                'number':   t.number,
                'name':     t.name,
                'stage':    t.stage_id.name if t.stage_id else '',
                'closed':   t.stage_id.closed if t.stage_id else False,
                'user':     t.user_id.name if t.user_id else '',
                'team':     t.team_id.name if t.team_id else '',
                'priority': t.priority,
                'type':     t.type_id.name if hasattr(t, 'type_id') and t.type_id else '',
                'date':     t.create_date.strftime('%d/%m/%y') if t.create_date else '',
            })
        return {'rows': rows}
