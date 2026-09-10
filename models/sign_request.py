# -*- coding: utf-8 -*-

import logging
from urllib.parse import urlencode

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SignRequest(models.Model):
    _inherit = 'sign.request'

    cs_document_id = fields.Many2one(
        'documents.document', string='Documento de sesión',
        readonly=True, copy=False, index=True, ondelete='set null')
    cs_signer_mobile = fields.Char(
        string='Móvil del firmante', compute='_compute_cs_signer_mobile')

    @api.depends('request_item_ids.state',
                 'request_item_ids.partner_id.mobile',
                 'request_item_ids.partner_id.phone')
    def _compute_cs_signer_mobile(self):
        for request in self:
            partner = request._cs_get_signer_item().partner_id
            request.cs_signer_mobile = partner.mobile or partner.phone or False

    def _cs_get_signer_item(self):
        """Firmante al que hay que reclamar la firma: el primero pendiente y,
        si ya no queda ninguno, el primero de la petición."""
        self.ensure_one()
        pending = self.request_item_ids.filtered(lambda item: item.state == 'sent')
        return pending[:1] or self.request_item_ids[:1]

    def _whatsapp_get_portal_url(self):
        """Enlace tokenizado de firma del firmante pendiente, para las plantillas
        de WhatsApp con variable de tipo 'Enlace del portal'.

        Lleva la misma firma de caducidad que el enlace que Odoo manda por correo,
        así que caduca según el parámetro 'sign.link_expiry_duration' (48 h por defecto).
        """
        self.ensure_one()
        item = self._cs_get_signer_item().sudo()
        if not item:
            return super()._whatsapp_get_portal_url()
        timestamp = item._generate_expiry_link_timestamp()
        params = urlencode({
            'timestamp': timestamp,
            'exp': item._generate_expiry_signature(item.id, timestamp),
        })
        return 'sign/document/mail/%s/%s?%s' % (self.id, item.access_token, params)

    def _wa_get_safe_phone_fields(self):
        return super()._wa_get_safe_phone_fields() + ['cs_signer_mobile']

    def cs_send_signature_whatsapp(self):
        """Envía al firmante pendiente la plantilla de WhatsApp con el enlace de firma.

        Mientras la plantilla no esté aprobada por Meta no se envía nada: la petición
        de firma ya está creada y se puede reclamar por los medios habituales.
        """
        template = self.env.ref(
            'cs_gabinete_firma.whatsapp_template_firma_sesion', raise_if_not_found=False)
        if not template or template.status != 'approved' or not template.wa_account_id:
            _logger.warning(
                "Gabinetes: no se envía el enlace de firma por WhatsApp porque la plantilla "
                "«Firma de sesión de gabinete» no está aprobada en Meta o no tiene cuenta asociada.")
            return self.env['whatsapp.message']
        messages = self.env['whatsapp.message']
        for request in self.filtered('cs_signer_mobile'):
            composer = self.env['whatsapp.composer'].with_context(
                active_model='sign.request', active_ids=request.ids,
            ).create({
                'res_model': 'sign.request',
                'res_ids': str(request.ids),
                'wa_template_id': template.id,
                'phone': request.cs_signer_mobile,
            })
            messages |= composer._send_whatsapp_template(force_send_by_cron=True)
        return messages
