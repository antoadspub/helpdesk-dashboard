from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from collections import defaultdict
import json


class HelpdeskDashboard(http.Controller):

    def _check_manager_access(self):
        user = request.env.user
        is_manager = user.has_group('helpdesk_mgmt.group_helpdesk_manager')
        is_agent = user.has_group('helpdesk_mgmt.group_helpdesk_user')
        return is_manager or is_agent

    @http.route('/helpdesk/dashboard', type='http', auth='user', website=False)
    def dashboard(self, **kwargs):
        if not self._check_manager_access():
            return request.not_found()
        return request.render('helpdesk_dashboard.dashboard_main', {})

    @http.route('/helpdesk/dashboard/data', type='json', auth='user')
    def dashboard_data(self, period=1, team_id=None, **kwargs):
        if not self._check_manager_access():
            return {'error': 'Access denied'}

        Ticket = request.env['helpdesk.ticket']
        date_from = datetime.now() - timedelta(days=int(period) * 30)

        # Base domain for period filter
        domain_period = [('create_date', '>=', date_from)]
        if team_id and team_id != 'all':
            domain_period.append(('team_id', '=', int(team_id)))

        # All open (not closed) tickets - no date filter
        domain_open = [('closed', '=', False)]
        if team_id and team_id != 'all':
            domain_open.append(('team_id', '=', int(team_id)))

        all_tickets = Ticket.search(domain_period)
        open_tickets = Ticket.search(domain_open)

        # --- Metric cards ---
        total = len(open_tickets)
        assigned = len(open_tickets.filtered(lambda t: t.user_id and t.stage_id.name not in ['Done', 'Cancelled', 'Resolved']))
        resolved = len(all_tickets.filtered(lambda t: t.stage_id.name in ['Done', 'Resolved', 'Closed']))
        unassigned = len(open_tickets.filtered(lambda t: not t.user_id))

        # --- By assigned tech (ongoing) ---
        tech_ongoing = defaultdict(int)
        for t in open_tickets.filtered(lambda t: t.user_id):
            tech_ongoing[t.user_id.name] += 1
        tech_ongoing_sorted = sorted(tech_ongoing.items(), key=lambda x: x[1], reverse=True)[:8]

        # --- By assigned tech (period) ---
        tech_period = defaultdict(int)
        for t in all_tickets.filtered(lambda t: t.user_id):
            tech_period[t.user_id.name] += 1
        tech_period_sorted = sorted(tech_period.items(), key=lambda x: x[1], reverse=True)[:8]

        # --- By hour of day ---
        hour_counts = defaultdict(int)
        for t in all_tickets:
            if t.create_date:
                hour_counts[t.create_date.hour] += 1
        hours_with_data = sorted(hour_counts.items())
        hour_labels = [f"{h:02d}:00" for h, _ in hours_with_data]
        hour_data = [c for _, c in hours_with_data]

        # --- By date opened ---
        date_counts = defaultdict(int)
        for t in all_tickets:
            if t.create_date:
                date_counts[t.create_date.strftime('%d/%m/%y')] += 1
        date_sorted = sorted(date_counts.items(), key=lambda x: datetime.strptime(x[0], '%d/%m/%y'))[-10:]
        date_labels = [d for d, _ in date_sorted]
        date_data = [c for _, c in date_sorted]

        # --- By status ---
        stage_counts = defaultdict(int)
        for t in open_tickets:
            stage_counts[t.stage_id.name] += 1
        status_labels = list(stage_counts.keys())
        status_data = list(stage_counts.values())

        # --- By location (team) ---
        location_counts = defaultdict(int)
        for t in all_tickets:
            loc = t.team_id.name if t.team_id else 'No Team'
            location_counts[loc] += 1
        location_sorted = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        location_labels = [l for l, _ in location_sorted]
        location_data = [c for _, c in location_sorted]

        # --- By ticket type ---
        type_counts = defaultdict(int)
        for t in all_tickets:
            type_name = t.type_id.name if hasattr(t, 'type_id') and t.type_id else 'No Type'
            type_counts[type_name] += 1
        type_sorted = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        type_labels = [tp for tp, _ in type_sorted]
        type_data = [c for _, c in type_sorted]

        # --- Recent activity ---
        recent = Ticket.search(domain_period, order='write_date desc', limit=10)
        activity = []
        for t in recent:
            activity.append({
                'id': t.id,
                'number': t.number if hasattr(t, 'number') else t.id,
                'name': t.name,
                'stage': t.stage_id.name,
                'user': t.user_id.name if t.user_id else 'Unassigned',
                'partner': t.partner_id.name if t.partner_id else '',
                'date': t.write_date.strftime('%d/%m/%y %H:%M') if t.write_date else '',
                'priority': t.priority if hasattr(t, 'priority') else '0',
            })

        # --- Teams list for filter ---
        teams = request.env['helpdesk.team'].search([])
        teams_list = [{'id': t.id, 'name': t.name} for t in teams]

        return {
            'metrics': {
                'total': total,
                'assigned': assigned,
                'resolved': resolved,
                'unassigned': unassigned,
            },
            'tech_ongoing': {
                'labels': [x[0] for x in tech_ongoing_sorted],
                'data': [x[1] for x in tech_ongoing_sorted],
            },
            'tech_period': {
                'labels': [x[0] for x in tech_period_sorted],
                'data': [x[1] for x in tech_period_sorted],
            },
            'hour': {'labels': hour_labels, 'data': hour_data},
            'date': {'labels': date_labels, 'data': date_data},
            'status': {'labels': status_labels, 'data': status_data},
            'location': {'labels': location_labels, 'data': location_data},
            'type': {'labels': type_labels, 'data': type_data},
            'activity': activity,
            'teams': teams_list,
        }
