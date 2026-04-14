{
    'name': 'Helpdesk Manager Dashboard',
    'version': '18.0.1.0.0',
    'summary': 'Live dashboard for helpdesk managers and team leaders',
    'author': 'Custom',
    'depends': ['helpdesk_mgmt', 'helpdesk_type', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'templates/dashboard_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'helpdesk_dashboard/static/src/css/dashboard.css',
            'helpdesk_dashboard/static/src/js/dashboard.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
