/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class DashboardBuilderAction extends Component {
    static template = "helpdesk_dashboard_builder.DashboardBuilderAction";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ loading: true, layout: null, widgets: [] });
        this.draggedWidget = null;
        this.loadDashboard();
    }

    async loadDashboard() {
        this.state.loading = true;
        const data = await this.orm.call("helpdesk.dashboard.controller", "get_dashboard_data", []);
        this.state.layout = data.layout;
        this.state.widgets = data.widgets || [];
        this.state.loading = false;
    }

    widthClass(width) {
        return {
            full: "o_hd_col_full",
            half: "o_hd_col_half",
            third: "o_hd_col_third",
        }[width] || "o_hd_col_half";
    }

    onDragStart(ev, widget) {
        this.draggedWidget = widget;
        ev.dataTransfer.effectAllowed = "move";
    }

    onDragOver(ev) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
    }

    async onDrop(ev, targetWidget) {
        ev.preventDefault();
        if (!this.draggedWidget || this.draggedWidget.id === targetWidget.id) {
            return;
        }
        const widgets = [...this.state.widgets];
        const sourceIndex = widgets.findIndex((w) => w.id === this.draggedWidget.id);
        const targetIndex = widgets.findIndex((w) => w.id === targetWidget.id);
        const [moved] = widgets.splice(sourceIndex, 1);
        widgets.splice(targetIndex, 0, moved);
        this.state.widgets = widgets;

        if (this.state.layout?.id) {
            await this.orm.call("helpdesk.dashboard.controller", "save_widget_order", [
                this.state.layout.id,
                widgets.map((w) => w.id),
            ]);
            this.notification.add("Widget order updated", { type: "success" });
        }
    }
}

registry.category("actions").add("helpdesk_dashboard_builder.action", DashboardBuilderAction);
