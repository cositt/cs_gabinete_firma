# -*- coding: utf-8 -*-

import logging
from datetime import datetime, time, timedelta

from pytz import timezone, utc

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    cs_sign_request_id = fields.Many2one(
        'sign.request', string='Petición de firma',
        readonly=True, copy=False, ondelete='set null')
    cs_sign_state = fields.Selection(
        related='cs_sign_request_id.state', string='Estado de la firma')

    def action_cs_request_session_signature(self):
        """Crea la petición de firma al tutor y le manda el enlace por WhatsApp."""
        requests = self._cs_create_session_sign_requests()
        requests.cs_send_signature_whatsapp()
        if len(requests) == 1:
            return requests.go_to_document()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Firmas de sesión"),
            'res_model': 'sign.request',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', requests.ids)],
        }

    def _cs_create_session_sign_requests(self):
        requests = self.env['sign.request']
        for document in self:
            requests |= document._cs_create_session_sign_request()
        return requests

    def _cs_create_session_sign_request(self):
        self.ensure_one()
        if self.cs_sign_request_id:
            return self.cs_sign_request_id
        if not self.attachment_id:
            raise UserError(_("El documento «%s» no tiene ningún archivo adjunto.", self.name))

        signer = self._cs_get_signer()
        if not signer:
            raise UserError(_(
                "El contacto del documento «%s» no tiene tutor asignado ni sirve como firmante.",
                self.name))

        master = self.company_id.cs_gabinete_sign_template_id or \
            self.env.company.cs_gabinete_sign_template_id
        if not master:
            raise UserError(_(
                "Configure la plantilla de firma de sesión en los ajustes de Documentos."))

        # documents_sign deja que sign.template se apropie del adjunto de un documento,
        # así que se le entrega una copia para no vaciar el documento de origen.
        attachment = self.attachment_id.copy({'res_model': False, 'res_id': False})
        template = self.env['sign.template'].create({
            'name': self.name,
            'attachment_id': attachment.id,
            'folder_id': master.folder_id.id,
            'documents_tag_ids': [Command.set(master.documents_tag_ids.ids)],
        })
        master._copy_sign_items_to(template)

        roles = template.sign_item_ids.responsible_id
        if not roles:
            roles = self.env.ref('sign.sign_item_role_default')

        sign_request = self.env['sign.request'].with_context(no_sign_mail=True).create({
            'template_id': template.id,
            'reference': self.name,
            'subject': _("Conformidad de sesión: %s", self.name),
            'cs_document_id': self.id,
            'request_item_ids': [
                Command.create({'partner_id': signer.id, 'role_id': role.id})
                for role in roles
            ],
        })
        self.cs_sign_request_id = sign_request
        return sign_request

    def _cs_get_signer(self):
        """Tutor de la persona atendida; si no lo hay, el propio contacto."""
        self.ensure_one()
        partner = self.partner_id
        return partner.cs_tutor_id or partner

    @api.model
    def _cron_cs_request_session_signatures(self):
        """Reclama al día siguiente la firma de las sesiones guardadas la víspera."""
        # Como con cualquier cron que hace commit parcial: en tests (o si alguna vez
        # se llama desde dentro de otra transacción) no debe tocar el cursor real,
        # o rompe los savepoints de aislamiento. Mismo patrón que usa sign._sign().
        auto_commit = not bool(config['test_enable'] or config['test_file'])
        for document in self._cs_get_documents_pending_signature():
            try:
                request = document._cs_create_session_sign_request()
                if auto_commit:
                    self.env.cr.commit()
            except Exception:  # noqa: BLE001 - una sesión con error no debe parar el resto
                if auto_commit:
                    self.env.cr.rollback()
                _logger.exception(
                    "Gabinetes: no se pudo crear la petición de firma del documento %s",
                    document.id)
                continue
            # El aviso por WhatsApp se intenta aparte para que un fallo de mensajería
            # nunca deshaga la petición de firma ya creada.
            try:
                request.cs_send_signature_whatsapp()
                if auto_commit:
                    self.env.cr.commit()
            except Exception:  # noqa: BLE001
                if auto_commit:
                    self.env.cr.rollback()
                _logger.exception(
                    "Gabinetes: petición de firma %s creada, pero falló el aviso por WhatsApp",
                    request.id)
        return True

    @api.model
    def _cs_get_documents_pending_signature(self, day=None):
        """Documentos de sesión guardados el día indicado (por defecto, ayer)."""
        folders = self.env['res.company'].search([]).cs_gabinete_folder_id
        if not folders:
            return self.env['documents.document']
        if day is None:
            day = fields.Date.subtract(fields.Date.context_today(self), days=1)
        tz = timezone(self.env.company.partner_id.tz or self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(day, time.min)).astimezone(utc)
        stop = tz.localize(datetime.combine(day + timedelta(days=1), time.min)).astimezone(utc)
        return self.search([
            ('folder_id', 'child_of', folders.ids),
            ('cs_sign_request_id', '=', False),
            ('attachment_id', '!=', False),
            ('partner_id', '!=', False),
            ('create_date', '>=', start.replace(tzinfo=None)),
            ('create_date', '<', stop.replace(tzinfo=None)),
        ])
