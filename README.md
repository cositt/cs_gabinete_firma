# cs_gabinete_firma

Módulo Odoo 17 para la Fundación Autismo Sur. Pide al tutor la conformidad de las
sesiones de gabinete (psicología, fisioterapia, logopedia...) por firma digital, y
le manda el enlace por WhatsApp.

## 1) Flujo funcional

1. El profesional guarda el documento de la sesión (PDF) en el espacio de trabajo
   **Gabinetes** de la app Documentos, asociado al contacto de la persona atendida.
2. Al día siguiente (o a mano, con el botón "Pedir firma de la sesión al tutor" en
   la lista/kanban de Documentos) el módulo:
   - Copia la plantilla maestra de firma configurada en la empresa.
   - Crea una `sign.request` dirigida al **tutor** del contacto (`cs_tutor_id`); si
     el contacto no tiene tutor asignado, se le pide la firma a él mismo.
   - Genera el enlace tokenizado de firma (mismo mecanismo de expiración que usa
     Odoo para el enlace por correo del módulo `sign`).
   - Manda el enlace por WhatsApp usando la plantilla `firma_sesion_gabinete`.

## 2) Dependencias

`documents_sign`, `whatsapp` (Odoo Enterprise/OEEL-1).

## 3) Configuración necesaria antes de usarlo

En **Ajustes > Documentos**:
- **Espacio de trabajo de gabinetes** (`cs_gabinete_folder_id`): por defecto la
  carpeta "Gabinetes" que crea el propio módulo.
- **Plantilla de firma de sesión** (`cs_gabinete_sign_template_id`): plantilla de
  `sign.template` con el campo de firma ya colocado en el PDF. **Obligatoria** —
  sin ella, tanto el botón manual como el cron lanzan `UserError`.

En cada contacto (res.partner): campo **Tutor o representante legal**
(`cs_tutor_id`).

### WhatsApp

La plantilla `cs_gabinete_firma.whatsapp_template_firma_sesion` tiene que estar
**aprobada por Meta** y tener una cuenta de WhatsApp Business asociada
(`wa_account_id`). Mientras no lo esté, el envío se salta en silencio (queda
logueado un warning) — la petición de firma se crea igual y se puede reclamar por
los medios habituales, solo no se avisa por WhatsApp.

### Cron

`ir_cron_pedir_firma_sesiones` reclama automáticamente las firmas de las sesiones
de ayer. Se instala **inactivo** a propósito — activarlo en Ajustes > Técnico >
Acciones programadas una vez la plantilla de WhatsApp esté aprobada.

## 4) Tests

```bash
odoo -c /etc/odoo/odoo.conf -d <db> -u cs_gabinete_firma \
  --test-enable --test-tags /cs_gabinete_firma --stop-after-init
```

`tests/test_gabinete_firma.py` cubre: creación de la petición de firma (y su
idempotencia), resolución del firmante (tutor o el propio contacto), validaciones
(sin adjunto / sin contacto / sin plantilla maestra), formato del enlace
tokenizado, envío de WhatsApp sin plantilla aprobada (no-op), y la selección
diaria del cron (solo ayer, no repite, ignora documentos sin contacto).

## 5) Notas de implementación

- `documents.document.attachment_id` **no se consume**: al crear la plantilla de
  firma se le entrega una *copia* del adjunto, así el documento de origen no se
  queda sin archivo (comportamiento por defecto de `sign.template`/`documents_sign`
  al apropiarse de un adjunto).
- `_cron_cs_request_session_signatures` hace commit/rollback por documento
  (aislar un fallo puntual del resto de la tanda), guardado detrás de
  `config['test_enable']` — mismo patrón que `sign.SignRequest._sign()` en el core,
  para no romper los savepoints de test ni de una eventual llamada anidada.
