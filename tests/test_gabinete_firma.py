# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import file_open


@tagged('post_install', '-at_install')
class TestGabineteFirmaCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        with file_open('sign/static/demo/sample_contract.pdf', 'rb') as pdf_file:
            cls.pdf_content = pdf_file.read()

        master_attachment = cls.env['ir.attachment'].create({
            'name': 'Acta de conformidad de sesion.pdf',
            'raw': cls.pdf_content,
        })
        # v19: el PDF de una plantilla vive en sign.document (document_ids), no en
        # sign.template.attachment_id, y los sign.item cuelgan del sign.document.
        cls.master_template = cls.env['sign.template'].create({
            'name': 'Acta de conformidad de sesion',
        })
        master_document = cls.env['sign.document'].create({
            'attachment_id': master_attachment.id,
            'template_id': cls.master_template.id,
        })
        cls.env['sign.item'].create({
            'document_id': master_document.id,
            'type_id': cls.env.ref('sign.sign_item_type_signature').id,
            'responsible_id': cls.env.ref('sign.sign_item_role_default').id,
            'required': True,
            'page': 1,
            'posX': 0.6,
            'posY': 0.85,
            'width': 0.2,
            'height': 0.05,
        })

        cls.folder = cls.env.ref('cs_gabinete_firma.documents_folder_gabinetes')
        cls.env.company.cs_gabinete_sign_template_id = cls.master_template
        cls.env.company.cs_gabinete_folder_id = cls.folder

        cls.tutora = cls.env['res.partner'].create({
            'name': 'Ana Ruiz Moreno',
            'phone': '+34 600 11 22 33',
            'email': 'ana.ruiz@example.com',
        })
        cls.atendido = cls.env['res.partner'].create({
            'name': 'Pablo Gomez',
            'cs_tutor_id': cls.tutora.id,
        })

    def _create_document(self, name='Sesion psicologia', partner=None, with_attachment=True):
        attachment = False
        if with_attachment:
            attachment = self.env['ir.attachment'].create({
                'name': '%s.pdf' % name,
                'raw': self.pdf_content,
            })
        return self.env['documents.document'].create({
            'name': name,
            'folder_id': self.folder.id,
            'partner_id': partner.id if partner else False,
            'attachment_id': attachment.id if attachment else False,
        })

    def _set_create_date(self, document, when):
        document.flush_recordset()
        self.env.cr.execute(
            'UPDATE documents_document SET create_date = %s WHERE id = %s',
            (when, document.id))
        document.invalidate_recordset()


class TestSessionSignRequest(TestGabineteFirmaCommon):

    def test_creates_request_for_tutor(self):
        document = self._create_document(partner=self.atendido)
        request = document._cs_create_session_sign_request()

        self.assertEqual(request.state, 'sent')
        self.assertEqual(request.request_item_ids.partner_id, self.tutora)
        self.assertEqual(document.cs_sign_request_id, request)
        self.assertEqual(request.cs_signer_mobile, self.tutora.phone)

    def test_does_not_consume_source_attachment(self):
        document = self._create_document(partner=self.atendido)
        original_datas = document.attachment_id.datas
        document._cs_create_session_sign_request()

        self.assertTrue(document.attachment_id.datas)
        self.assertEqual(document.attachment_id.datas, original_datas)

    def test_is_idempotent(self):
        document = self._create_document(partner=self.atendido)
        first = document._cs_create_session_sign_request()
        second = document._cs_create_session_sign_request()

        self.assertEqual(first, second)
        self.assertEqual(self.env['sign.request'].search_count(
            [('cs_document_id', '=', document.id)]), 1)

    def test_signer_falls_back_to_contact_without_tutor(self):
        sin_tutor = self.env['res.partner'].create({
            'name': 'Persona sin tutor',
            'phone': '+34 600 99 88 77',
        })
        document = self._create_document(partner=sin_tutor)
        request = document._cs_create_session_sign_request()

        self.assertEqual(request.request_item_ids.partner_id, sin_tutor)

    def test_missing_attachment_raises(self):
        document = self._create_document(partner=self.atendido, with_attachment=False)
        with self.assertRaises(UserError):
            document._cs_create_session_sign_request()

    def test_missing_partner_raises(self):
        document = self._create_document(partner=None)
        with self.assertRaises(UserError):
            document._cs_create_session_sign_request()

    def test_missing_master_template_raises(self):
        self.env.company.cs_gabinete_sign_template_id = False
        document = self._create_document(partner=self.atendido)
        with self.assertRaises(UserError):
            document._cs_create_session_sign_request()

    def test_portal_url_matches_sign_link_format(self):
        document = self._create_document(partner=self.atendido)
        request = document._cs_create_session_sign_request()
        item = request.request_item_ids

        url = request._whatsapp_get_portal_url()

        self.assertTrue(url.startswith('sign/document/mail/%s/%s?' % (request.id, item.access_token)))
        self.assertIn('timestamp=', url)
        self.assertIn('exp=', url)

    def test_whatsapp_send_without_approved_template_is_a_noop(self):
        document = self._create_document(partner=self.atendido)
        request = document._cs_create_session_sign_request()

        messages = request.cs_send_signature_whatsapp()

        self.assertFalse(messages)


class TestSessionSignatureCron(TestGabineteFirmaCommon):

    def test_pending_selects_only_the_given_day(self):
        document = self._create_document(partner=self.atendido)
        today = fields.Date.context_today(self.env['documents.document'])

        self.assertIn(document, self.env['documents.document']._cs_get_documents_pending_signature(day=today))
        self.assertNotIn(
            document,
            self.env['documents.document']._cs_get_documents_pending_signature(
                day=today - timedelta(days=1)))

    def test_excludes_documents_with_signature_already_requested(self):
        document = self._create_document(partner=self.atendido)
        document._cs_create_session_sign_request()
        today = fields.Date.context_today(self.env['documents.document'])

        self.assertNotIn(
            document,
            self.env['documents.document']._cs_get_documents_pending_signature(day=today))

    def test_excludes_documents_without_partner(self):
        document = self._create_document(partner=None)
        today = fields.Date.context_today(self.env['documents.document'])

        self.assertNotIn(
            document,
            self.env['documents.document']._cs_get_documents_pending_signature(day=today))

    def test_cron_creates_requests_for_yesterdays_sessions(self):
        document = self._create_document(partner=self.atendido)
        self._set_create_date(document, fields.Datetime.now() - timedelta(days=1))

        self.env['documents.document']._cron_cs_request_session_signatures()

        self.assertTrue(document.cs_sign_request_id)
        self.assertEqual(document.cs_sign_request_id.state, 'sent')

    def test_cron_ignores_todays_sessions(self):
        document = self._create_document(partner=self.atendido)

        self.env['documents.document']._cron_cs_request_session_signatures()

        self.assertFalse(document.cs_sign_request_id)


class TestPartnerTutorField(TransactionCase):
    """base.view_partner_form repite 'user_id' (el visible en Ventas y compras, y otro
    oculto dentro del subformulario de 'Añadir un contacto'). Un xpath anclado ahí cae en
    el primero que encuentre en orden de documento, que puede ser el oculto: el campo
    termina insertado donde ningún usuario lo ve nunca, aunque la instalación sea perfecta
    y los tests a nivel de ORM sigan en verde. Ver [[views/res_partner_views.xml]]."""

    def test_cs_tutor_id_is_not_nested_inside_a_subview(self):
        from lxml import etree

        view = self.env['res.partner'].get_view(
            view_id=self.env.ref('base.view_partner_form').id, view_type='form')
        arch = etree.fromstring(view['arch'])

        [tutor_field] = arch.xpath("//field[@name='cs_tutor_id']")
        for ancestor in tutor_field.iterancestors():
            self.assertNotEqual(
                ancestor.tag, 'field',
                "cs_tutor_id quedó anidado dentro de otro <field> (subformulario "
                "one2many) en vez de en el formulario principal del contacto.")


class TestV19DataModel(TestGabineteFirmaCommon):
    """Odoo 18+ eliminó documents.folder y documents.facet: las carpetas son
    documents.document con type='folder' y las etiquetas ya no tienen faceta."""

    def test_gabinetes_folder_is_a_folder_document(self):
        self.assertEqual(self.folder._name, 'documents.document')
        self.assertEqual(self.folder.type, 'folder')

    def test_company_folder_field_targets_documents(self):
        field = self.env['res.company']._fields['cs_gabinete_folder_id']
        self.assertEqual(field.comodel_name, 'documents.document')

    def test_session_tags_exist(self):
        self.assertTrue(self.env.ref('cs_gabinete_firma.documents_tag_sesion'))
        self.assertTrue(self.env.ref('cs_gabinete_firma.documents_tag_firmada'))

    def test_request_copies_master_sign_items(self):
        document = self._create_document(partner=self.atendido)
        request = document._cs_create_session_sign_request()
        self.assertTrue(request.template_id.sign_item_ids)
        self.assertNotEqual(request.template_id, self.master_template)

    def test_action_opens_list_view_mode(self):
        documents = self._create_document('S1', partner=self.atendido) | \
            self._create_document('S2', partner=self.atendido)
        action = documents.action_cs_request_session_signature()
        self.assertNotIn('tree', action['view_mode'])
