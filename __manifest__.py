# -*- coding: utf-8 -*-
{
    'name': "Gabinetes: firma de sesiones",

    'summary': "Pide al tutor que firme la conformidad de las sesiones de gabinete y le envía el enlace por WhatsApp.",

    'description': """
Firma de sesiones de gabinete
=============================

El profesional guarda el documento de la sesión en el espacio de trabajo Gabinetes.
Al día siguiente el módulo crea una petición de firma dirigida al tutor de la persona
atendida y le envía por WhatsApp el enlace tokenizado para firmarla.
""",

    'author': "Cositt Technology",
    'maintainer': 'Cositt Technology',
    'website': "https://cositt.com",

    'category': 'Autismosur/Gabinetes',
    'version': '17.0.1.0.0',

    'depends': ['documents_sign', 'whatsapp'],

    'data': [
        'data/documents_data.xml',
        'data/whatsapp_template_data.xml',
        'data/ir_cron_data.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/documents_document_views.xml',
    ],

    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}
