/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";

const CHART_COLORS = {
    blue:   '#378ADD', amber:  '#EF9F27', green:  '#639922',
    purple: '#534AB7', teal:   '#1D9E75', coral:  '#D85A30',
};
const PIE_PALETTE = ['#378ADD','#EF9F27','#1D9E75','#FAC775','#534AB7','#D85A30','#639922','#9FE1CB'];
const GRID   = 'rgba(120,120,120,0.1)';
const TLABEL = '#888780';

const WIDGET_TYPES = [
    { type:'counter',     name:'Counter Card',    desc:'Single metric number' },
    { type:'bar',         name:'Bar Chart',        desc:'Group tickets by field' },
    { type:'donut',       name:'Donut Chart',      desc:'Breakdown by category' },
    { type:'line',        name:'Trend Chart',      desc:'Tickets over time' },
    { type:'leaderboard', name:'Leaderboard',      desc:'Top engineers ranking' },
    { type:'activity',    name:'Activity Feed',    desc:'Recent ticket events' },
    { type:'table',       name:'Ticket Table',     desc:'List of tickets' },
];

function stageBadge(row) {
    const s = (row.stage || '').toLowerCase();
    if (row.closed)                                   return 'hd2-badge-closed';
    if (s.includes('assign'))                         return 'hd2-badge-assigned';
    if (s.includes('resolv') || s.includes('done'))   return 'hd2-badge-resolved';
    return 'hd2-badge-open';
}

function emptyForm(type) {
    return {
        widget_type: type || 'counter',
        title: '',
        size: 'half',
        color: 'blue',
        period: '1',
        team_filter: '',
        group_by: 'user',
        metric: 'open',
        filter_open: false,
        limit: 10,
    };
}

// Plain JSON-RPC helper — works in Odoo 18 CE without useService('rpc')
async function jsonRpc(route, params) {
    const response = await fetch(route, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            id: Math.floor(Math.random() * 1e9),
            params: params || {},
        }),
    });
    const json = await response.json();
    if (json.error) throw new Error(json.error.data?.message || json.error.message);
    return json.result;
}

export class HdDashboard extends Component {
    static template = "hd_dashboard.Dashboard";

    setup() {
        this.state = useState({
            loading: true,
            widgets: [],
            teams: [],
            editMode: false,
            sidebarOpen: false,
            editingWidget: null,
            newWidgetType: null,
            isManager: false,
            form: emptyForm(),
        });
        this.charts      = {};
        this.dragSrcId   = null;
        this.widgetTypes = WIDGET_TYPES;
        onMounted(() => this.init());
    }

    async init() {
        await this.loadChartJs();
        await this.loadLayout();
    }

    loadChartJs() {
        return new Promise(resolve => {
            if (window.Chart) { resolve(); return; }
            const s = document.createElement('script');
            s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';
            s.onload = resolve;
            document.head.appendChild(s);
        });
    }

    async loadLayout() {
        this.state.loading = true;
        try {
            const data = await jsonRpc('/hd/dashboard/layout/get', {});
            if (!data || data.error) return;
            this.state.teams     = data.teams || [];
            this.state.isManager = data.is_manager || false;
            this.state.widgets   = data.widgets.map(w => ({
                ...w, _loading: true, _data: null,
            }));
            this.fetchAllWidgets();
        } catch(e) {
            console.error('Dashboard load error', e);
        } finally {
            this.state.loading = false;
        }
    }

    async fetchAllWidgets() {
        for (const w of this.state.widgets) {
            this.fetchWidget(w);
        }
    }

    async fetchWidget(widget) {
        widget._loading = true;
        try {
            const data = await jsonRpc('/hd/dashboard/widget/data', { widget });
            widget._data = data;
            if (['bar','donut','line'].includes(widget.widget_type)) {
                setTimeout(() => this.renderChart(widget), 100);
            }
        } catch(e) {
            console.error('Widget fetch error', widget.title, e);
            widget._data = null;
        } finally {
            widget._loading = false;
        }
    }

    // ─── Chart rendering ─────────────────────────────────────────────

    destroyChart(id) {
        if (this.charts[id]) { this.charts[id].destroy(); delete this.charts[id]; }
    }

    renderChart(widget) {
        if (!widget._data) return;
        const canvas = document.getElementById('chart-' + widget.id);
        if (!canvas) return;
        this.destroyChart(widget.id);
        const { labels, data } = widget._data;
        if (!labels || !data) return;
        const color  = CHART_COLORS[widget.color] || CHART_COLORS.blue;
        const limit  = parseInt(widget.limit) || 10;

        if (widget.widget_type === 'donut') {
            canvas.parentElement.style.height = '200px';
            this.charts[widget.id] = new window.Chart(canvas, {
                type: 'doughnut',
                data: { labels, datasets: [{ data, backgroundColor: PIE_PALETTE, borderWidth: 2, borderColor: '#fff' }] },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: '58%',
                    plugins: { legend: { display: true, position: 'bottom', labels: { font:{size:10}, boxWidth:10, padding:8 } } },
                },
            });
        } else if (widget.widget_type === 'line') {
            canvas.parentElement.style.height = '180px';
            this.charts[widget.id] = new window.Chart(canvas, {
                type: 'line',
                data: { labels, datasets: [{ data, borderColor: color, backgroundColor: color+'33', tension:.3, fill:true, pointRadius:3 }] },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid:{display:false}, ticks:{color:TLABEL, font:{size:10}, maxRotation:35} },
                        y: { grid:{color:GRID},    ticks:{color:TLABEL, font:{size:11}} },
                    },
                },
            });
        } else {
            const isHoriz = !['date','hour'].includes(widget.group_by);
            const sl = isHoriz
                ? { labels: labels.slice(0, limit), data: data.slice(0, limit) }
                : { labels, data };
            const h = isHoriz ? Math.max(sl.labels.length * 36 + 40, 80) : 180;
            canvas.parentElement.style.height = h + 'px';
            this.charts[widget.id] = new window.Chart(canvas, {
                type: 'bar',
                data: { labels: sl.labels, datasets: [{ data: sl.data, backgroundColor: color, borderRadius:4, barThickness:20 }] },
                options: {
                    indexAxis: isHoriz ? 'y' : 'x',
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: isHoriz ? {color:GRID} : {display:false}, ticks:{color:TLABEL, font:{size:10}, maxRotation:35, autoSkip:false} },
                        y: { grid: isHoriz ? {display:false} : {color:GRID}, ticks:{color:TLABEL, font:{size:11}} },
                    },
                },
            });
        }
    }

    // ─── Edit mode ───────────────────────────────────────────────────

    toggleEdit() { this.state.editMode = !this.state.editMode; }

    async refreshAll() { await this.fetchAllWidgets(); }

    async resetLayout() {
        if (!confirm('Reset to default layout? Your personal layout will be removed.')) return;
        await jsonRpc('/hd/dashboard/layout/reset', {});
        await this.loadLayout();
    }

    async saveMine() {
        await this._saveLayout(false);
        alert('Personal layout saved!');
    }

    async saveDefault() {
        if (!confirm('Save this layout as the default for all users?')) return;
        await this._saveLayout(true);
        alert('Default layout saved for all users!');
    }

    async _saveLayout(asDefault) {
        const widgets = this.state.widgets.map((w, i) => ({
            widget_type:  w.widget_type,
            title:        w.title,
            position:     i + 1,
            size:         w.size,
            color:        w.color,
            group_by:     w.group_by || null,
            metric:       w.metric   || 'open',
            period:       w.period   || '1',
            team_filter:  w.team_filter || null,
            filter_open:  w.filter_open || false,
            limit:        parseInt(w.limit) || 10,
        }));
        await jsonRpc('/hd/dashboard/layout/save', { widgets, save_as_default: asDefault });
    }

    // ─── Add / Edit widget ───────────────────────────────────────────

    openAddWidget() {
        this.state.editingWidget = null;
        this.state.newWidgetType = null;
        this.state.form = emptyForm();
        this.state.sidebarOpen = true;
    }

    selectWidgetType(type) {
        this.state.newWidgetType = type;
        this.state.form = emptyForm(type);
        this.state.form.title = WIDGET_TYPES.find(w => w.type === type)?.name || 'Widget';
    }

    openEditWidget(widget) {
        this.state.editingWidget = widget;
        this.state.newWidgetType = null;
        this.state.form = {
            widget_type: widget.widget_type,
            title:       widget.title,
            size:        widget.size,
            color:       widget.color,
            period:      widget.period      || '1',
            team_filter: widget.team_filter || '',
            group_by:    widget.group_by    || 'user',
            metric:      widget.metric      || 'open',
            filter_open: widget.filter_open || false,
            limit:       widget.limit       || 10,
        };
        this.state.sidebarOpen = true;
    }

    saveWidget() {
        const f = this.state.form;
        if (!f.title.trim()) { alert('Please enter a title.'); return; }
        if (this.state.editingWidget) {
            const w = this.state.editingWidget;
            Object.assign(w, {
                title: f.title, size: f.size, color: f.color,
                period: f.period, team_filter: f.team_filter || null,
                group_by: f.group_by, metric: f.metric,
                filter_open: f.filter_open, limit: parseInt(f.limit) || 10,
            });
            this.destroyChart(w.id);
            this.fetchWidget(w);
        } else if (this.state.newWidgetType) {
            const newW = {
                id: 'new_' + Date.now(),
                widget_type: this.state.newWidgetType,
                title:       f.title,
                size:        f.size,
                color:       f.color,
                period:      f.period,
                team_filter: f.team_filter || null,
                group_by:    f.group_by,
                metric:      f.metric,
                filter_open: f.filter_open,
                limit:       parseInt(f.limit) || 10,
                position:    this.state.widgets.length + 1,
                _loading:    true,
                _data:       null,
            };
            this.state.widgets.push(newW);
            this.fetchWidget(newW);
        }
        this.closeSidebar();
    }

    removeWidget(widget) {
        if (!confirm('Remove this widget?')) return;
        this.destroyChart(widget.id);
        const idx = this.state.widgets.indexOf(widget);
        if (idx > -1) this.state.widgets.splice(idx, 1);
    }

    closeSidebar() {
        this.state.sidebarOpen  = false;
        this.state.editingWidget = null;
        this.state.newWidgetType = null;
    }

    formType() {
        return this.state.editingWidget
            ? this.state.editingWidget.widget_type
            : this.state.newWidgetType;
    }

    // ─── Drag and drop ───────────────────────────────────────────────

    onDragStart(e, widget) {
        this.dragSrcId = widget.id;
        e.currentTarget.classList.add('hd2-dragging');
    }

    onDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('hd2-drag-over');
    }

    onDragLeave(e) {
        e.currentTarget.classList.remove('hd2-drag-over');
    }

    onDrop(e, targetWidget) {
        e.currentTarget.classList.remove('hd2-drag-over');
        if (!this.dragSrcId || this.dragSrcId === targetWidget.id) return;
        const srcIdx = this.state.widgets.findIndex(w => w.id === this.dragSrcId);
        const tgtIdx = this.state.widgets.findIndex(w => w.id === targetWidget.id);
        if (srcIdx < 0 || tgtIdx < 0) return;
        const [moved] = this.state.widgets.splice(srcIdx, 1);
        this.state.widgets.splice(tgtIdx, 0, moved);
        this.dragSrcId = null;
        setTimeout(() => {
            this.state.widgets.forEach(w => {
                if (['bar','donut','line'].includes(w.widget_type) && w._data) {
                    this.renderChart(w);
                }
            });
        }, 100);
    }

    // ─── Helpers ─────────────────────────────────────────────────────

    stageBadge(row) { return stageBadge(row); }
}

registry.category("actions").add("hd_dashboard", HdDashboard);
