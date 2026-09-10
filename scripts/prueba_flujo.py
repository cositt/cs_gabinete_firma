import base64

from odoo import Command

PDF = '/mnt/enterprise-addons/sign/static/demo/sample_contract.pdf'
with open(PDF, 'rb') as fh:
    DATA = base64.b64encode(fh.read())

company = env.company  # noqa: F821

print('--- 1. plantilla maestra de firma ---')
master_att = env['ir.attachment'].create({  # noqa: F821
    'name': 'Acta de conformidad de sesion.pdf',
    'datas': DATA,
    'mimetype': 'application/pdf',
})
master = env['sign.template'].create({  # noqa: F821
    'name': 'Acta de conformidad de sesion',
    'attachment_id': master_att.id,
})
role = env.ref('sign.sign_item_role_default')  # noqa: F821
env['sign.item'].create({  # noqa: F821
    'template_id': master.id,
    'type_id': env.ref('sign.sign_item_type_signature').id,  # noqa: F821
    'responsible_id': role.id,
    'required': True,
    'page': 1,
    'posX': 0.6,
    'posY': 0.85,
    'width': 0.2,
    'height': 0.05,
})
folder = env.ref('cs_gabinete_firma.documents_folder_gabinetes')  # noqa: F821
company.cs_gabinete_sign_template_id = master
company.cs_gabinete_folder_id = folder
print('   plantilla:', master.name, '| items de firma:', len(master.sign_item_ids))

print('--- 2. contactos: persona atendida y tutora ---')
tutora = env['res.partner'].create({  # noqa: F821
    'name': 'Ana Ruiz Moreno',
    'mobile': '+34 600 11 22 33',
    'email': 'ana.ruiz@example.com',
})
atendido = env['res.partner'].create({  # noqa: F821
    'name': 'Pablo Gomez',
    'cs_tutor_id': tutora.id,
})
print('   atendido:', atendido.name, '| tutora:', atendido.cs_tutor_id.name, atendido.cs_tutor_id.mobile)

print('--- 3. documento de la sesion en el espacio Gabinetes ---')
doc_att = env['ir.attachment'].create({  # noqa: F821
    'name': 'Sesion psicologia 2026-08-06.pdf',
    'datas': DATA,
    'mimetype': 'application/pdf',
})
documento = env['documents.document'].create({  # noqa: F821
    'name': 'Sesion psicologia 2026-08-06',
    'folder_id': folder.id,
    'partner_id': atendido.id,
    'attachment_id': doc_att.id,
    'tag_ids': [Command.set(env.ref('cs_gabinete_firma.documents_tag_sesion').ids)],  # noqa: F821
})
print('   documento:', documento.name, '| adjunto:', documento.attachment_id.name)

print('--- 4. peticion de firma dirigida a la tutora ---')
peticion = documento._cs_create_session_sign_request()
print('   peticion:', peticion.reference, '| estado:', peticion.state)
print('   firmante:', peticion.request_item_ids.partner_id.name)
print('   movil detectado:', peticion.cs_signer_mobile)
print('   documento sigue con adjunto:', bool(documento.attachment_id.datas))
print('   enlace guardado en el documento:', documento.cs_sign_request_id.id == peticion.id)

print('--- 5. enlace tokenizado ---')
ruta = peticion._whatsapp_get_portal_url()
print('   ruta:', ruta)

print('--- 6. render de la plantilla de WhatsApp ---')
plantilla = env.ref('cs_gabinete_firma.whatsapp_template_firma_sesion')  # noqa: F821
valores = plantilla.variable_ids._get_variables_value(peticion)
for clave, valor in sorted(valores.items()):
    print('   ', clave, '=>', valor)

cuerpo = plantilla.body
for indice, clave in enumerate(['body-{{1}}', 'body-{{2}}', 'body-{{3}}'], start=1):
    cuerpo = cuerpo.replace('{{%s}}' % indice, valores.get(clave, ''))
print('   MENSAJE FINAL:', cuerpo)

print('--- 7. datos para verificar por HTTP ---')
env.cr.commit()  # noqa: F821 - el shell descarta la transacción al salir
print('URL_PRUEBA=%s' % valores.get('body-{{3}}'))
