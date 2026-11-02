// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export const DELIVERY_RECOVERY_SPANISH: Record<string, string> = {
  'A stable request key is required. Review the original request before continuing.':
    'Se necesita una clave estable para la solicitud. Revisa la solicitud original antes de continuar.',
  'Email service and receipt': 'Servicio de correo y recepción',
  'Refresh recorded checks': 'Actualizar comprobaciones registradas',
  'An email service can accept a message without confirming that the recipient received it. A check reads the existing provider operation; it does not resend the message.':
    'El servicio de correo puede aceptar un mensaje sin confirmar que la persona lo haya recibido. La comprobación consulta la operación existente del proveedor; no vuelve a enviar el mensaje.',
  'Loading delivery checks': 'Cargando comprobaciones de entrega',
  'View new welcome': 'Consultar nueva bienvenida',
  'New delivery reference': 'Referencia del nuevo envío',
  'Provider observation': 'Observación del proveedor',
  'Recipient receipt': 'Recepción por la persona destinataria',
  'No check recorded': 'Sin comprobaciones registradas',
  'Not confirmed': 'Sin confirmar',
  'Last checked': 'Última comprobación',
  'Check email service': 'Comprobar servicio de correo',
  'Send a new welcome': 'Enviar una nueva bienvenida',
  'A request needs confirmation': 'Hay una solicitud pendiente de confirmar',
  'Refreshing or signing in never repeats a saved request. Inspect the delivery, then review the original request if its result is still unknown.':
    'Actualizar o iniciar sesión no repite una solicitud guardada. Consulta la entrega y revisa la solicitud original si su resultado sigue sin confirmarse.',
  'Review saved request': 'Revisar solicitud guardada',
  'Review delivery action': 'Revisar acción de entrega',
  'This uses the exact saved request and its original key. If the service already accepted it, it returns the recorded result. If it did not, it may perform the reviewed action.':
    'Utiliza la solicitud exacta y su clave original. Si el servicio ya la aceptó, devuelve el resultado registrado. Si no la había aceptado, puede realizar la acción revisada.',
  'Confirm with the recipient before sending another welcome. This queues a new message for the current approved recipient and preserves the original delivery and its attempts.':
    'Confírmalo con la persona destinataria antes de enviar otra bienvenida. Se preparará un nuevo mensaje para el destinatario aprobado actualmente y se conservarán la entrega original y sus intentos.',
  'The recipient reported that the welcome did not arrive. I understand both messages may arrive.':
    'La persona destinataria ha indicado que no recibió la bienvenida. Entiendo que pueden llegar ambos mensajes.',
  'Read the retained operation status from the configured email service. This check does not send another email or confirm inbox placement.':
    'Consulta el estado de la operación conservada en el servicio de correo configurado. No envía otro mensaje ni confirma su llegada a la bandeja de entrada.',
  Cancel: 'Cancelar',
  'Queue new welcome': 'Preparar nueva bienvenida',
  'Recorded provider checks': 'Comprobaciones registradas del proveedor',
  'Only the 25 most recent checks are shown.': 'Se muestran las 25 comprobaciones más recientes.',
  'Check in progress': 'Comprobación en curso',
  'Provider operation pending': 'Operación del proveedor pendiente',
  'Accepted by email service': 'Aceptado por el servicio de correo',
  'Rejected by email service': 'Rechazado por el servicio de correo',
  'Provider outcome unknown': 'Resultado del proveedor sin confirmar',
  'Provider status unavailable': 'Estado del proveedor no disponible',
  'Your current account cannot inspect or manage this delivery.':
    'Tu cuenta actual no puede consultar ni gestionar esta entrega.',
  'The request result is not confirmed. Inspect this delivery before reviewing the exact saved request.':
    'El resultado de la solicitud no está confirmado. Consulta esta entrega antes de revisar la solicitud exacta guardada.',
  'The delivery could not be inspected. Refresh its details before continuing.':
    'No se ha podido consultar la entrega. Actualiza sus detalles antes de continuar.',
  'Saved delivery requests could not be verified. This browser tab must support session storage before making changes.':
    'No se han podido verificar las solicitudes guardadas. Esta pestaña debe admitir almacenamiento de sesión antes de realizar cambios.',
  'This delivery changed. Inspect its current options before confirming another action.':
    'La entrega ha cambiado. Consulta sus opciones actuales antes de confirmar otra acción.',
  'Email service observation recorded. This does not confirm that the recipient received the message.':
    'Se ha registrado la observación del servicio de correo. No confirma que la persona haya recibido el mensaje.',
  'A new welcome was queued. The earlier delivery is unchanged and may still arrive. Mailbox receipt is not confirmed.':
    'Se ha preparado una nueva bienvenida. La entrega anterior se conserva y todavía puede llegar. La recepción en el buzón no está confirmada.',
  'The request was not accepted. Inspect current delivery options before choosing another action.':
    'La solicitud no se ha aceptado. Consulta las opciones actuales de la entrega antes de elegir otra acción.',
  'The configured email service cannot inspect this operation.':
    'El servicio de correo configurado no puede consultar esta operación.',
  'A deployment operator must verify the original email service before a new check.':
    'Un operador del despliegue debe verificar el servicio de correo original antes de realizar otra comprobación.',
  'The email service changed. A deployment operator must review the original operation.':
    'El servicio de correo ha cambiado. Un operador del despliegue debe revisar la operación original.',
  'The delivery changed. Refresh its details before continuing.':
    'La entrega ha cambiado. Actualiza sus detalles antes de continuar.',
  'A recent check already exists. Wait before requesting another check.':
    'Ya existe una comprobación reciente. Espera antes de solicitar otra.',
  'The earlier check did not complete. Its result remains unknown.':
    'La comprobación anterior no terminó. Su resultado sigue sin confirmarse.',
  'The check was cancelled. No recipient receipt was established.':
    'La comprobación se canceló. No se ha confirmado la recepción por la persona destinataria.',
  'The saved inspection request differs. Refresh the delivery before continuing.':
    'La solicitud de comprobación guardada no coincide. Actualiza la entrega antes de continuar.',
  'The email service did not return a usable status.':
    'El servicio de correo no ha devuelto un estado válido.',
  'The retained operation could not be verified.':
    'No se ha podido verificar la operación conservada.',
  'The email service receipt could not be verified.':
    'No se ha podido verificar el comprobante del servicio de correo.',
  'The email service rejected the operation.': 'El servicio de correo ha rechazado la operación.',
  'This request key belongs to a different welcome recovery.':
    'La clave de esta solicitud corresponde a otra recuperación de bienvenida.',
  'The welcome or approved contact changed. Refresh before reviewing another request.':
    'La bienvenida o el contacto aprobado han cambiado. Actualiza antes de revisar otra solicitud.',
  'A recent welcome recovery exists. Review it before requesting another welcome.':
    'Ya existe una recuperación reciente. Revísala antes de solicitar otra bienvenida.',
  'A deployment operator must review this welcome before it can be recovered.':
    'Un operador del despliegue debe revisar esta bienvenida antes de recuperarla.',
  'A current approved recipient is required before sending another welcome.':
    'Se necesita un destinatario aprobado y vigente antes de enviar otra bienvenida.',
  'This delivery is not an eligible welcome.':
    'Esta entrega no es una bienvenida que pueda recuperarse.',
  'The email service or sender needs configuration before another welcome can be queued.':
    'Es necesario configurar el servicio de correo o el remitente antes de preparar otra bienvenida.',
  'The recipient is no longer eligible for this operation.':
    'La persona destinataria ya no cumple los requisitos para esta operación.',
  'No action is available. Ask a deployment operator to inspect this delivery.':
    'No hay ninguna acción disponible. Pide a un operador del despliegue que revise esta entrega.',
};
