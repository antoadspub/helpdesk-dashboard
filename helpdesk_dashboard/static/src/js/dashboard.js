/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

const PIE  = ['#378ADD','#EF9F27','#1D9E75','#D85A30','#534AB7','#E24B4A','#639922','#FAC775','#9FE1CB','#F4C0D1'];
const BARS = ['#378ADD','#EF9F27','#1D9E75','#D85A30','#534AB7','#E24B4A','#639922','#BA7517','#0F6E56','#993C1D'];
const SOLO = {blue:'#378ADD',amber:'#EF9F27',green:'#639922',purple:'#534AB7',teal:'#1D9E75',coral:'#D85A30'};
const GRID = 'rgba(120,120,120,0.1)', TXT = '#888780';

const W_TYPES = [
    {type:'counter',name:'Counter Card',desc:'Single metric number'},
    {type:'bar',name:'Bar Chart',desc:'Group tickets by field'},
    {type:'donut',name:'Donut Chart',desc:'Breakdown by category'},
    {type:'line',name:'Trend Chart',desc:'Tickets over time'},
    {type:'leaderboard',name:'Leaderboard',desc:'Top engineers ranking'},
    {type:'activity',name:'Activity Feed',desc:'Recent ticket events'},
    {type:'table',name:'Ticket Table',desc:'List of tickets'},
];
const F_FIELDS = [
    {key:'stage',label:'Stage'},{key:'user',label:'Assigned to'},
    {key:'team',label:'Team'},{key:'priority',label:'Priority'},
    {key:'type',label:'Ticket Type'},{key:'category',label:'Category'},
    {key:'closed',label:'Is Closed'},
];

function sbName(n,c){
    if(c) return 'hd2-badge-closed';
    const s=(n||'').toLowerCase();
    if(s.includes('progress')||s.includes('assign')) return 'hd2-badge-assigned';
    if(s.includes('resolv')||s.includes('done')) return 'hd2-badge-resolved';
    return 'hd2-badge-open';
}
function sb(r){ if(r.closed)return'hd2-badge-closed'; if(r.unattended)return'hd2-badge-open'; if(r.user)return'hd2-badge-assigned'; return'hd2-badge-open'; }
function pl(p){return{'0':'Low','1':'Medium','2':'High','3':'Very High'}[p]||p;}
function ef(t){return{widget_type:t||'counter',title:'',size:'half',color:'blue',period:'1',team_filter:'',group_by:'user',metric:'open',filter_open:false,limit:10,adv_filters:[]};}
function efilter(){return{id:Date.now(),logic:'AND',field:'stage',op:'=',value:''};}

async function rpc(route, params){
    const r = await fetch(route, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({jsonrpc:'2.0',method:'call',id:Math.random()*1e9|0,params:params||{}}),
    });
    const j = await r.json();
    if(j.error) throw new Error(j.error.data?.message||j.error.message);
    return j.result;
}

// Chart instances stored completely outside OWL reactive state
const CHARTS = {};

function destroyChart(id){
    if(CHARTS[id]){
        // Remove event listener before destroying
        if(CHARTS[id]._clickHandler && CHARTS[id]._canvas){
            CHARTS[id]._canvas.removeEventListener('click', CHARTS[id]._clickHandler);
        }
        CHARTS[id].destroy();
        delete CHARTS[id];
    }
}

function buildChart(canvasId, type, groupBy, colorKey, limit, labels, data, onClickFn){
    const canvas = document.getElementById(canvasId);
    if(!canvas){ console.warn('Canvas not found:', canvasId); return; }

    destroyChart(canvasId);

    // Ensure canvas has explicit dimensions — fixes small widget blank issue
    const parentEl = canvas.parentElement;
    const parentWidth = parentEl ? parentEl.offsetWidth : 200;

    const isTime  = groupBy==='date' || groupBy==='hour';
    const solo    = SOLO[colorKey] || SOLO.blue;
    const lim     = parseInt(limit)||10;

    // Plain arrays — no proxy involvement
    const L = (type==='bar' && !isTime) ? labels.slice(0,lim) : [...labels];
    const D = (type==='bar' && !isTime) ? data.slice(0,lim)   : [...data];

    const bgDonut = PIE.slice(0, L.length);
    const bgBar   = isTime ? solo : L.map((_,i)=>BARS[i%BARS.length]);

    // Chart options with legend and tooltip color box both off
    const basePlugins = {
        legend: { display: false },
        tooltip: {
            displayColors: false,
            callbacks: {
                title: (items) => items[0]?.label || '',
                label: (ctx)  => `${ctx.formattedValue||ctx.parsed} tickets`,
            },
        },
    };

    let cfg;

    if(type==='donut'){
        const h = Math.max(parentWidth * 0.8, 180);
        parentEl.style.height = h + 'px';
        cfg = {
            type: 'doughnut',
            data: {
                labels: L,
                datasets:[{ data:D, backgroundColor:bgDonut, borderWidth:2, borderColor:'#fff' }],
            },
            options:{
                responsive:true, maintainAspectRatio:false, cutout:'55%',
                plugins:{
                    // Donut gets its own legend showing each segment
                    legend:{
                        display: L.length > 0,
                        position:'bottom',
                        labels:{
                            font:{size:10}, boxWidth:10, padding:8,
                            generateLabels:(ch)=>{
                                const bg = ch.data.datasets[0].backgroundColor;
                                return ch.data.labels.map((text,i)=>({
                                    text, fillStyle: Array.isArray(bg)?bg[i]:bg,
                                    strokeStyle:'#fff', lineWidth:1, hidden:false,
                                    datasetIndex:0, index:i,
                                }));
                            },
                        },
                    },
                    tooltip:{ displayColors:false, callbacks:{
                        title:(items)=>items[0]?.label||'',
                        label:(ctx)=>`${ctx.parsed} tickets`,
                    }},
                },
            },
        };
    } else if(type==='line'){
        parentEl.style.height = Math.max(parentWidth*0.6, 150)+'px';
        cfg = {
            type:'line',
            data:{ labels:L, datasets:[{data:D,borderColor:solo,backgroundColor:solo+'33',tension:.3,fill:true,pointRadius:3}] },
            options:{
                responsive:true, maintainAspectRatio:false,
                plugins: basePlugins,
                scales:{
                    x:{grid:{display:false},ticks:{color:TXT,font:{size:10},maxRotation:45}},
                    y:{grid:{color:GRID},ticks:{color:TXT,font:{size:11}}},
                },
            },
        };
    } else {
        // bar
        const isHoriz = !isTime;
        if(isHoriz){
            parentEl.style.height = Math.max(L.length*36+40, 100)+'px';
        } else {
            parentEl.style.height = Math.max(parentWidth*0.6, 150)+'px';
        }
        cfg = {
            type:'bar',
            data:{ labels:L, datasets:[{data:D, backgroundColor:bgBar, borderRadius:4, barThickness:isHoriz?18:'flex'}] },
            options:{
                indexAxis: isHoriz?'y':'x',
                responsive:true, maintainAspectRatio:false,
                plugins: basePlugins,
                scales:{
                    x:{ grid:isHoriz?{color:GRID}:{display:false}, ticks:{color:TXT,font:{size:10},maxRotation:45,autoSkip:false} },
                    y:{ grid:isHoriz?{display:false}:{color:GRID}, ticks:{color:TXT,font:{size:11}} },
                },
            },
        };
    }

    // Create chart — use Chart from Odoo's registry if available, else window.Chart
    const ChartCls = window.Chart;
    if(!ChartCls){ console.error('Chart.js not available'); return; }

    const chart = new ChartCls(canvas, cfg);
    CHARTS[canvasId] = chart;

    // Fix clicks: use addEventListener NOT canvas.onclick
    // Store reference so we can remove it on destroy
    const labelsSnap = [...L];
    const clickHandler = function(e){
        e.stopPropagation();
        const pts = chart.getElementsAtEventForMode(e, 'nearest', {intersect: type==='donut'}, true);
        if(pts.length > 0){
            const lbl = labelsSnap[pts[0].index];
            if(lbl !== undefined) onClickFn(lbl);
        }
    };
    CHARTS[canvasId]._clickHandler = clickHandler;
    CHARTS[canvasId]._canvas = canvas;
    canvas.style.cursor = 'pointer';
    canvas.addEventListener('click', clickHandler);
}

function drawChartWhenReady(canvasId, type, groupBy, colorKey, limit, labels, data, onClickFn, tries=12){
    const exists = document.getElementById(canvasId);
    if(exists){
        buildChart(canvasId, type, groupBy, colorKey, limit, labels, data, onClickFn);
        return;
    }
    if(tries <= 0){
        console.warn('Chart canvas never became available:', canvasId);
        return;
    }
    setTimeout(()=>{
        drawChartWhenReady(canvasId, type, groupBy, colorKey, limit, labels, data, onClickFn, tries-1);
    }, 120);
}

export class HdDashboard extends Component {
    static template = "hd_dashboard.Dashboard";

    setup(){
        this.state = useState({
            loading:true,
            widgets:[], teams:[], stages:[], users:[], types:[], categories:[],
            editMode:false,
            sidebarOpen:false, editingWidget:null, newWidgetType:null,
            isManager:false,
            form:ef(),
            drilldown:null,
        });
        this.actionService = useService("action");
        this.dragSrcId   = null;
        this.widgetTypes  = W_TYPES;
        this.filterFields = F_FIELDS;
        onMounted(()=>this.init());
    }

    async init(){
        // Load Chart.js via Odoo's asset loader — uses the version Odoo already bundles
        try {
            await loadJS('https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js');
        } catch(e){
            // If CDN fails, window.Chart may already be available from Odoo
        }
        if(!window.Chart){ console.error('Chart.js failed to load'); return; }
        // Set global defaults ONCE — eliminates undefined legend everywhere
        window.Chart.defaults.plugins.legend.display = false;
        window.Chart.defaults.plugins.tooltip.displayColors = false;
        await this.loadLayout();
    }

    async loadLayout(){
        this.state.loading = true;
        try{
            const d = await rpc('/hd/dashboard/layout/get', {});
            if(!d || d.error) return;
            this.state.teams      = d.teams      || [];
            this.state.stages     = d.stages     || [];
            this.state.users      = d.users      || [];
            this.state.types      = d.types      || [];
            this.state.categories = d.categories || [];
            this.state.isManager  = d.is_manager || false;
            this._ticketActionId = d.ticket_action_id || false;
            this.state.widgets    = d.widgets.map(w=>({...w,_loading:true,_data:null}));
            await this.fetchAllWidgets();
        } catch(e){ console.error('loadLayout', e); }
        finally{ this.state.loading = false; }
    }

    async fetchAllWidgets(){
        for(const w of this.state.widgets) await this.fetchWidget(w);
    }

    async fetchWidget(widget){
        widget._loading = true;
        // Capture ALL values as plain primitives before any await
        const id         = String(widget.id);
        const wtype      = String(widget.widget_type);
        const groupBy    = String(widget.group_by   || '');
        const colorKey   = String(widget.color      || 'blue');
        const metric     = String(widget.metric     || 'open');
        const period     = String(widget.period     || '1');
        const teamFilter = widget.team_filter ? String(widget.team_filter) : null;
        const filterOpen = Boolean(widget.filter_open);
        const limit      = parseInt(widget.limit)   || 10;
        const advFilters = JSON.parse(JSON.stringify(widget.adv_filters||[]));
        const snap = {id, widget_type:wtype, group_by:groupBy, metric, period,
                      team_filter:teamFilter, filter_open:filterOpen, limit, adv_filters:advFilters};
        try{
            const result = await rpc('/hd/dashboard/widget/data', {widget:snap});
            widget._data = result;
            if(['bar','donut','line'].includes(wtype) && result?.labels?.length){
                drawChartWhenReady(
                    'chart-'+id, wtype, groupBy, colorKey, limit,
                    result.labels, result.data,
                    (label)=>this.doDrilldown(label,{
                        group_by:groupBy, period, team_filter:teamFilter,
                        filter_open:filterOpen, adv_filters:advFilters,
                    })
                );
            }
        } catch(e){
            console.error('fetchWidget', wtype, e);
            widget._data = null;
        } finally {
            widget._loading = false;
        }
    }

    async doDrilldown(label, meta){
        try{
            const r = await rpc('/hd/dashboard/widget/drilldown', {
                group_by:    meta.group_by,
                label,
                period:      meta.period      || '1',
                team_filter: meta.team_filter || null,
                filter_open: meta.filter_open || false,
                adv_filters: meta.adv_filters || [],
            });
            const ids = r.ids || (r.rows||[]).map(row=>row.id);
            if(!ids.length){
                alert('No tickets found for: ' + label);
                return;
            }
            // Use Odoo 18 web client URL format with action ID and domain in hash
            // This opens the native Odoo list view properly filtered
            const actionId = this._ticketActionId;
            const domain   = JSON.stringify([['id','in', ids]]);
            // Open filtered ticket list — 'current' target so clicking a row
            // opens the form view and tickets can be edited directly
            await this.actionService.doAction({
                type:        'ir.actions.act_window',
                name:        'Tickets: ' + label,
                res_model:   'helpdesk.ticket',
                view_mode:   'list,form',
                views:       [[false, 'list'], [false, 'form']],
                domain:      [['id', 'in', ids]],
                target:      'current',
                context: {
                    create: false,
                },
            }, {
                onClose: () => { /* back to dashboard */ }
            });
        } catch(e){
            console.error('drilldown error', e);
        }
    }

    closeDrilldown(){ this.state.drilldown = null; }
    dbadge(r)         { return sbName(r.stage, r.closed); }
    drilldownBadge(r) { return sbName(r.stage, r.closed); }
    openTicket(id){
        this.actionService.doAction({
            type:      'ir.actions.act_window',
            res_model: 'helpdesk.ticket',
            res_id:    id,
            views:     [[false, 'form']],
            target:    'current',
        });
    }

    getFieldOptions(field){
        const m = {
            stage:    this.state.stages.map(s=>({v:s.name,l:s.name})),
            team:     this.state.teams.map(t=>({v:t.name,l:t.name})),
            user:     this.state.users.map(u=>({v:u.name,l:u.name})),
            priority: [{v:'0',l:'Low'},{v:'1',l:'Medium'},{v:'2',l:'High'},{v:'3',l:'Very High'}],
            type:     this.state.types.map(t=>({v:t.name,l:t.name})),
            category: this.state.categories.map(c=>({v:c.name,l:c.name})),
            closed:   [{v:'true',l:'Yes (Closed)'},{v:'false',l:'No (Open)'}],
        };
        return m[field]||[];
    }
    addFormFilter()    { this.state.form.adv_filters.push(efilter()); }
    removeFormFilter(f){ const i=this.state.form.adv_filters.indexOf(f); if(i>-1)this.state.form.adv_filters.splice(i,1); }
    onFFField(f,ev)    { f.field=ev.target.value; f.value=''; }
    onFFOp(f,ev)       { f.op=ev.target.value; }
    onFFVal(f,ev)      { f.value=ev.target.value; }
    onFFLogic(f,ev)    { f.logic=ev.target.value; }
    // Backward-compatible handlers referenced by the template
    onFormFilterField(f,ev){ this.onFFField(f,ev); }
    onFormFilterOp(f,ev)   { this.onFFOp(f,ev); }
    onFormFilterVal(f,ev)  { this.onFFVal(f,ev); }
    onFormFilterLogic(f,ev){ this.onFFLogic(f,ev); }

    filterSummary(w){
        const p=[];
        if(w.period&&w.period!=='1') p.push({'3':'3mo','6':'6mo','12':'12mo','0':'All time'}[w.period]||w.period);
        if(w.team_filter_name) p.push(w.team_filter_name);
        if(w.filter_open)      p.push('Open only');
        const a=w.adv_filters||[];
        if(a.length) p.push(`+${a.length} filter${a.length>1?'s':''}`);
        return p.join(' · ');
    }

    toggleEdit(){ this.state.editMode=!this.state.editMode; }
    async refreshAll(){ await this.fetchAllWidgets(); }
    async resetLayout(){ if(!confirm('Reset to default layout?'))return; await rpc('/hd/dashboard/layout/reset',{}); await this.loadLayout(); }
    async saveMine()   { await this._save(false); alert('Personal layout saved!'); }
    async saveDefault(){ if(!confirm('Save as default for all users?'))return; await this._save(true); alert('Default layout saved!'); }

    async _save(asDefault){
        const ws=this.state.widgets.map((w,i)=>({
            widget_type:w.widget_type, title:w.title, position:i+1,
            size:w.size, color:w.color, group_by:w.group_by||null,
            metric:w.metric||'open', period:w.period||'1',
            team_filter:w.team_filter||null, filter_open:w.filter_open||false,
            limit:parseInt(w.limit)||10,
            adv_filters:JSON.parse(JSON.stringify(w.adv_filters||[])),
        }));
        await rpc('/hd/dashboard/layout/save',{widgets:ws,save_as_default:asDefault});
    }

    openAddWidget(){
        this.state.editingWidget=null; this.state.newWidgetType=null;
        this.state.form=ef(); this.state.sidebarOpen=true;
    }
    selectWidgetType(type){
        this.state.newWidgetType=type;
        this.state.form=ef(type);
        this.state.form.title=W_TYPES.find(w=>w.type===type)?.name||'Widget';
    }
    openEditWidget(widget){
        this.state.editingWidget=widget; this.state.newWidgetType=null;
        this.state.form={
            widget_type:  widget.widget_type,
            title:        widget.title,
            size:         widget.size,
            color:        widget.color,
            period:       widget.period      || '1',
            team_filter:  widget.team_filter ? String(widget.team_filter) : '',
            group_by:     widget.group_by    || 'user',
            metric:       widget.metric      || 'open',
            filter_open:  widget.filter_open || false,
            limit:        widget.limit       || 10,
            adv_filters:  JSON.parse(JSON.stringify(widget.adv_filters||[])),
        };
        this.state.sidebarOpen=true;
    }
    saveWidget(){
        const f=this.state.form;
        if(!f.title.trim()){ alert('Enter a title.'); return; }
        const team=this.state.teams.find(t=>String(t.id)===String(f.team_filter));
        const props={
            title:f.title, size:f.size, color:f.color, period:f.period,
            team_filter:f.team_filter||null, team_filter_name:team?team.name:'',
            group_by:f.group_by, metric:f.metric, filter_open:f.filter_open,
            limit:parseInt(f.limit)||10,
            adv_filters:JSON.parse(JSON.stringify(f.adv_filters||[])),
        };
        if(this.state.editingWidget){
            const w=this.state.editingWidget;
            Object.assign(w,props);
            destroyChart('chart-'+w.id);
            this.fetchWidget(w);
        } else if(this.state.newWidgetType){
            const nw={id:'new_'+Date.now(),widget_type:this.state.newWidgetType,
                ...props,position:this.state.widgets.length+1,_loading:true,_data:null};
            this.state.widgets.push(nw);
            this.fetchWidget(nw);
        }
        this.closeSidebar();
    }
    removeWidget(widget){
        if(!confirm('Remove this widget?'))return;
        destroyChart('chart-'+widget.id);
        const i=this.state.widgets.indexOf(widget);
        if(i>-1)this.state.widgets.splice(i,1);
    }
    closeSidebar(){
        this.state.sidebarOpen=false;
        this.state.editingWidget=null; this.state.newWidgetType=null;
    }
    formType(){ return this.state.editingWidget?this.state.editingWidget.widget_type:this.state.newWidgetType; }

    onDragStart(e,w){
        this.dragSrcId=String(w.id);
        if(e.dataTransfer){
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.dropEffect = 'move';
            e.dataTransfer.setData('text/plain', this.dragSrcId);
        }
        e.currentTarget.classList.add('hd2-dragging');
    }
    onDragEnd(e){
        this.dragSrcId = null;
        e.currentTarget.classList.remove('hd2-dragging');
        document.querySelectorAll('.hd2-drag-over').forEach(el=>el.classList.remove('hd2-drag-over'));
    }
    onDragOver(e)   { e.preventDefault(); e.currentTarget.classList.add('hd2-drag-over'); }
    onDragLeave(e)  { e.currentTarget.classList.remove('hd2-drag-over'); }
    onDrop(e,tw){
        e.preventDefault();
        e.currentTarget.classList.remove('hd2-drag-over');
        const targetId = String(tw.id);
        if(!this.dragSrcId||this.dragSrcId===targetId)return;
        const si=this.state.widgets.findIndex(w=>String(w.id)===this.dragSrcId);
        const ti=this.state.widgets.findIndex(w=>String(w.id)===targetId);
        if(si<0||ti<0)return;
        const[m]=this.state.widgets.splice(si,1);
        this.state.widgets.splice(ti,0,m);
        this.dragSrcId=null;
        setTimeout(()=>{
            this.state.widgets.forEach(w=>{
                if(['bar','donut','line'].includes(w.widget_type)&&w._data?.labels?.length){
                    const g=String(w.group_by||''),c=String(w.color||'blue'),
                          p=String(w.period||'1'),tf=w.team_filter?String(w.team_filter):null,
                          fo=Boolean(w.filter_open),af=JSON.parse(JSON.stringify(w.adv_filters||[]));
                    buildChart('chart-'+w.id,w.widget_type,g,c,w.limit,w._data.labels,w._data.data,
                        (label)=>this.doDrilldown(label,{group_by:g,period:p,team_filter:tf,filter_open:fo,adv_filters:af}));
                }
            });
        },300);
    }

    stageBadge(r)   { return sb(r); }
    priorityLabel(p){ return pl(p); }
}

const actionRegistry = registry.category("actions");
actionRegistry.add("hd_dashboard", HdDashboard, { force: true });
// Backward-compatible alias for environments/databases that may still reference a namespaced tag
actionRegistry.add("helpdesk_dashboard.hd_dashboard", HdDashboard, { force: true });
