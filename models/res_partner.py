# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cs_tutor_id = fields.Many2one(
        'res.partner',
        string='Tutor o representante legal',
        help="Contacto que firma la conformidad de las sesiones de gabinete de esta persona.")
