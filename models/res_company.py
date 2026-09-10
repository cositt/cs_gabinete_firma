# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cs_gabinete_folder_id = fields.Many2one(
        'documents.folder', string='Espacio de trabajo de gabinetes',
        default=lambda self: self.env.ref(
            'cs_gabinete_firma.documents_folder_gabinetes', raise_if_not_found=False),
        help="Espacio de trabajo donde los profesionales guardan los documentos de sesión.")
    cs_gabinete_sign_template_id = fields.Many2one(
        'sign.template', string='Plantilla de firma de sesión',
        help="Plantilla con el campo de firma que firmará el tutor.")
