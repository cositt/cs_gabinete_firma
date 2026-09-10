from datetime import timedelta

from odoo import fields

Documento = env['documents.document']  # noqa: F821
folder = env.ref('cs_gabinete_firma.documents_folder_gabinetes')  # noqa: F821
hoy = fields.Date.context_today(Documento)
ayer = fields.Date.subtract(hoy, days=1)

print('--- 1. seleccion del cron ---')
de_hoy = Documento._cs_get_documents_pending_signature(day=hoy)
de_ayer = Documento._cs_get_documents_pending_signature(day=ayer)
print('   documentos de hoy pendientes :', de_hoy.mapped('name'))
print('   documentos de ayer pendientes:', de_ayer.mapped('name'))

print('--- 2. no repite los que ya tienen firma pedida ---')
firmado = Documento.search([('cs_sign_request_id', '!=', False)], limit=1)
print('   documento con firma ya pedida:', firmado.name, '| lo excluye:',
      firmado not in Documento._cs_get_documents_pending_signature(day=hoy))

print('--- 2b. caso positivo: sesion de ayer con contacto y tutor ---')
tutora = env['res.partner'].search([('name', '=', 'Ana Ruiz Moreno')], limit=1)  # noqa: F821
atendido = env['res.partner'].search([('name', '=', 'Pablo Gomez')], limit=1)  # noqa: F821
valido = Documento.create({
    'name': 'Sesion fisioterapia de ayer',
    'folder_id': folder.id,
    'partner_id': atendido.id,
    'datas': env['documents.document'].search(  # noqa: F821
        [('cs_sign_request_id', '!=', False)], limit=1).attachment_id.datas,
    'mimetype': 'application/pdf',
})
valido.flush_recordset()
env.cr.execute(  # noqa: F821
    "UPDATE documents_document SET create_date = %s WHERE id = %s",
    (fields.Datetime.now() - timedelta(days=1), valido.id))
valido.invalidate_recordset()
print('   el cron SI lo selecciona:', valido in Documento._cs_get_documents_pending_signature(day=ayer))

print('--- 3. documento de ayer sin partner: se ignora ---')
sin_contacto = Documento.create({
    'name': 'Sesion sin contacto',
    'folder_id': folder.id,
    'datas': firmado.attachment_id.datas,
    'mimetype': 'application/pdf',
})
sin_contacto.flush_recordset()
env.cr.execute(  # noqa: F821
    "UPDATE documents_document SET create_date = %s WHERE id = %s",
    (fields.Datetime.now() - timedelta(days=1), sin_contacto.id))
sin_contacto.invalidate_recordset()
print('   se ignora por no tener contacto:',
      sin_contacto not in Documento._cs_get_documents_pending_signature(day=ayer))

print('--- 4. envio de WhatsApp SIN cuenta de Meta configurada ---')
print('   cuentas de WhatsApp en la base:', env['whatsapp.account'].search_count([]))  # noqa: F821
peticion = env['sign.request'].search([('cs_document_id', '!=', False)], limit=1)  # noqa: F821
try:
    mensajes = peticion.cs_send_signature_whatsapp()
    print('   RESULTADO: no lanza excepcion. Mensajes creados:', len(mensajes))
    for mensaje in mensajes:
        print('   estado:', mensaje.state, '| motivo:', mensaje.failure_type or '-')
except Exception as error:  # noqa: BLE001
    print('   RESULTADO: LANZA EXCEPCION ->', type(error).__name__, error)

env.cr.rollback()  # noqa: F821
