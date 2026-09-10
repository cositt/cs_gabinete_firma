# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cs_gabinete_folder_id = fields.Many2one(
        related='company_id.cs_gabinete_folder_id', readonly=False)
    cs_gabinete_sign_template_id = fields.Many2one(
        related='company_id.cs_gabinete_sign_template_id', readonly=False)
