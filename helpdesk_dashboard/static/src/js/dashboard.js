/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState, useRef } from "@odoo/owl";

const COLORS = {
    blue:   '#378ADD',
    amber:  '#EF9F27',
    green:  '#639922',
    purple: '#534AB7',
    teal:   '#1D9E75',
    coral:  '#D85A30',
    pink:   '#D4537E',
    ltBlue: '#85B7EB',
    ltAmber:'#FAC775',
    ltTeal: '#9FE1CB',
};

const PIE_COLORS = [COLORS.blue, COLORS.amber, COLORS.teal, COLORS.ltAmber, COLORS.purple, COLORS.coral];
const GRID_COLOR = 'rgba(120,120,120,0.1)';
const TEXT_COLOR = '#888780';

function stageBadgeClass(stage) {
    const s = (stage || '').toLowerCase();
    if (s.includes('open'))     return 'hd-badge-open';
    if (s.includes('assign'))   return 'hd-badge-assigned';
    if (s.includes('resolv') || s.includes('done')) return 'hd-badge-resolved';
    if (s.includes('clos') || s.includes('cancel')) return 'hd-badge-closed';
    return 'hd-badge-default';
}

class HelpdeskDashboard extends Component {
    static template = "helpdesk_dashboard.Dashboard";

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            loading: true,
            period: '1',
            teamId: 'all',
            teams: [],
            metrics: { total: 0, assigned: 0, resolved: 0, unassigned: 0 },
            activity: [],
        });
        this.charts = {};
        this.canvasRefs = {
            techOngoing: useRef('techOngoing'),
            techPeriod:  useRef('techPeriod'),
            hour:        useRef('hour'),
            date:        useRef('date'),
            status:      useRef('status'),
            location:    useRef('location'),
            type:        useRef('type'),
        };
        onMounted(() => this.loadChartJs());
    }

    loadChartJs() {
        if (window.Chart) {
            this.fetchData();
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';
        script.onload = () => this.fetchData();
        document.head.appendChild(script);
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const data = await this.rpc('/helpdesk/dashboard/data', {
                period: this.state.period,
                team_id: this.state.teamId,
            });
            if (data.error) return;
            this.state.metrics = data.metrics;
            this.state.activity = data.activity;
            if (data.teams && data.teams.length) this.state.teams = data.teams;
            this.renderCharts(data);
        } finally {
            this.state.loading = false;
        }
    }

    destroyChart(key) {
        if (this.charts[key]) {
            this.charts[key].destroy();
            delete this.charts[key];
        }
    }

    hbar(key, labels, data, color) {
        this.destroyChart(key);
        const canvas = this.canvasRefs[key].el;
        if (!canvas) return;
        const barH = Math.max(labels.length * 36 + 40, 120);
        canvas.parentElement.style.height = barH + 'px';
        this.charts[key] = new window.Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: color,
                    borderRadius: 4,
                    barThickness: 20,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: {
                    label: ctx => ` ${ctx.parsed.x} tickets`
                }}},
                scales: {
                    x: { grid: { color: GRID_COLOR }, ticks: { color: TEXT_COLOR, font: { size: 11 } } },
                    y: { grid: { display: false }, ticks: { color: TEXT_COLOR, font: { size: 11 } } },
                },
            },
        });
    }

    vbar(key, labels, data, color) {
        this.destroyChart(key);
        const canvas = this.canvasRefs[key].el;
        if (!canvas) return;
        canvas.parentElement.style.height = '180px';
        this.charts[key] = new window.Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{ data, backgroundColor: color, borderRadius: 4, barThickness: 22 }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: TEXT_COLOR, font: { size: 10 }, maxRotation: 35, autoSkip: false } },
                    y: { grid: { color: GRID_COLOR }, ticks: { color: TEXT_COLOR, font: { size: 11 } } },
                },
            },
        });
    }

    donut(key, labels, data, colors) {
        this.destroyChart(key);
        const canvas = this.canvasRefs[key].el;
        if (!canvas) return;
        canvas.parentElement.style.height = '160px';
        this.charts[key] = new window.Chart(canvas, {
            type: 'doughnut',
            data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 2, borderColor: '#fff' }] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '58%',
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed}` } },
                },
            },
        });
    }

    renderCharts(data) {
        // Small delay to ensure DOM is ready after state update
        setTimeout(() => {
            this.hbar('techOngoing', data.tech_ongoing.labels, data.tech_ongoing.data, COLORS.blue);
            this.hbar('techPeriod',  data.tech_period.labels,  data.tech_period.data,  COLORS.amber);
            this.vbar('hour', data.hour.labels, data.hour.data, COLORS.blue);
            this.vbar('date', data.date.labels, data.date.data, COLORS.green);
            this.donut('status',   data.status.labels,   data.status.data,   PIE_COLORS);
            this.donut('location', data.location.labels, data.location.data, PIE_COLORS);
            this.hbar('type', data.type.labels, data.type.data, COLORS.purple);
        }, 80);
    }

    onPeriodChange(ev) {
        this.state.period = ev.target.value;
        this.fetchData();
    }

    onTeamChange(ev) {
        this.state.teamId = ev.target.value;
        this.fetchData();
    }

    stageBadgeClass(stage) { return stageBadgeClass(stage); }
}

registry.category("actions").add("helpdesk_dashboard", HelpdeskDashboard);
