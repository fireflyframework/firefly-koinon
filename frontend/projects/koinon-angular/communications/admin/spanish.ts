// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export const COMMUNICATIONS_ADMIN_SPANISH: Readonly<Record<string, string>> = {
  'Email sender': 'Remitente del correo',
  'Use deployment default': 'Usar el predeterminado del despliegue',
  'Only senders verified in deployment configuration are available.':
    'Solo están disponibles los remitentes verificados en la configuración del despliegue.',
  'Choose an available verified sender.': 'Elige un remitente verificado disponible.',
  Communications: 'Comunicaciones',
  'Manage how invitations and access updates reach people in your organization.':
    'Gestiona cómo reciben las personas de tu organización las invitaciones y los avisos de acceso.',
  'Communications views': 'Vistas de comunicaciones',
  'Email service': 'Servicio de correo',
  Policies: 'Políticas',
  'Delivery history': 'Historial de envíos',
  'Loading communications': 'Cargando comunicaciones',
  'Email delivery': 'Envío de correo',
  Ready: 'Listo',
  'Needs attention': 'Requiere atención',
  Disabled: 'Desactivado',
  'Needs configuration': 'Requiere configuración',
  'Provider credentials and sender verification are managed in deployment configuration.':
    'Las credenciales del proveedor y la verificación del remitente se gestionan en la configuración del despliegue.',
  'Sender name': 'Nombre del remitente',
  'Sender address': 'Dirección del remitente',
  'Reply to': 'Responder a',
  'Uses sender address': 'Utiliza la dirección del remitente',
  'Public application address': 'Dirección pública de la aplicación',
  Configured: 'Configurada',
  'Not configured': 'Sin configurar',
  'Before email can be delivered': 'Antes de poder enviar correo',
  'Recipient eligibility is checked separately against the connected identity directory. A ready sender does not verify a recipient’s identity.':
    'La elegibilidad de la persona destinataria se comprueba por separado en el directorio de identidad conectado. Un remitente preparado no verifica la identidad de quien recibe el correo.',
  'Organization notification policy': 'Política de notificaciones de la organización',
  'Required notices protect people’s awareness of access changes. Personal preferences apply to the optional updates you enable.':
    'Los avisos obligatorios mantienen a las personas informadas de los cambios de acceso. Las preferencias personales se aplican a las novedades opcionales que habilites.',
  Required: 'Obligatorio',
  'In-app inbox': 'Bandeja de la aplicación',
  Email: 'Correo electrónico',
  'Allow optional knowledge digests': 'Permitir resúmenes opcionales del conocimiento',
  'People choose their own available digest schedule.':
    'Cada persona elige entre las frecuencias de resumen disponibles.',
  'Save policy': 'Guardar política',
  'Your role can view this policy. An administrator can change editable options.':
    'Tu rol permite consultar esta política. Una persona administradora puede cambiar las opciones editables.',
  'Delivery status': 'Estado del envío',
  'All statuses': 'Todos los estados',
  'All types': 'Todos los tipos',
  'From date': 'Desde la fecha',
  'To date': 'Hasta',
  'Apply filters': 'Aplicar filtros',
  Queued: 'En cola',
  Sending: 'Enviando',
  'Accepted by email service': 'Aceptado por el servicio de correo',
  Delivered: 'Entregado',
  Deferred: 'Aplazado',
  Failed: 'Fallido',
  Suppressed: 'Suprimido',
  Cancelled: 'Cancelado',
  'Outcome unknown': 'Resultado desconocido',
  Invitation: 'Invitación',
  'Access granted': 'Acceso concedido',
  'Role changed': 'Rol modificado',
  'Access removed': 'Acceso eliminado',
  'Knowledge digest': 'Resumen del conocimiento',
  'Recipient and update': 'Persona destinataria y aviso',
  'Email delivery records': 'Registros de envíos de correo',
  'No deliveries match these filters': 'No hay envíos con estos filtros',
  'Queued invitations and access updates will appear here. Try changing the status or dates.':
    'Las invitaciones y los avisos de acceso en cola aparecerán aquí. Prueba a cambiar el estado o las fechas.',
  'Delivery details': 'Detalles del envío',
  'Close delivery details': 'Cerrar detalles del envío',
  Recipient: 'Persona destinataria',
  Update: 'Aviso',
  Attempts: 'Intentos',
  'Last attempt': 'Último intento',
  'Next attempt': 'Próximo intento',
  'Retry this delivery? The email service may receive another attempt for this message.':
    '¿Reintentar este envío? El servicio de correo puede recibir otro intento para este mensaje.',
  'Retry delivery': 'Reintentar envío',
  'The end date must be on or after the start date.':
    'La fecha final debe ser igual o posterior a la fecha inicial.',
  Invitations: 'Invitaciones',
  'Access and security': 'Acceso y seguridad',
  'Knowledge updates': 'Novedades del conocimiento',
  'Invitations addressed to your existing directory account.':
    'Invitaciones dirigidas a tu cuenta existente del directorio.',
  'Changes to your role assignments and access to shared knowledge.':
    'Cambios en tus asignaciones de rol y acceso al conocimiento compartido.',
  'Optional summaries of activity you can currently access.':
    'Resúmenes opcionales de la actividad a la que tienes acceso actualmente.',
  'New role assignments that grant access to shared knowledge.':
    'Nuevas asignaciones de rol que conceden acceso al conocimiento compartido.',
  'Changes to your roles within an organization or workspace.':
    'Cambios en tus roles dentro de una organización o un espacio.',
  'Removal of a role assignment. Other roles may still grant access.':
    'Eliminación de una asignación de rol. Otros roles pueden seguir concediendo acceso.',
  'Default notification language': 'Idioma predeterminado de las notificaciones',
  'Use installation language': 'Usar el idioma de la instalación',
  'People can choose English or Spanish in their own notification preferences.':
    'Cada persona puede elegir inglés o español en sus preferencias de notificaciones.',
  'Allow optional usage summaries': 'Permitir resúmenes opcionales de uso',
  'People can turn summaries off or choose a schedule from the cadences you allow.':
    'Cada persona puede desactivar los resúmenes o elegir una frecuencia de las que permitas.',
  'Allowed summary schedules': 'Frecuencias permitidas para los resúmenes',
  'Summaries contain only the recipient’s own usage counts. Private content is never included.':
    'Los resúmenes solo contienen las cifras de uso de la persona destinataria. Nunca incluyen contenido privado.',
  'Default summary schedule': 'Frecuencia predeterminada del resumen',
  'Defaults apply until the person saves their own preferences. Off is always available.':
    'Los valores predeterminados se aplican hasta que la persona guarda sus preferencias. Siempre se pueden desactivar los resúmenes.',
  'Local send time follows each recipient’s profile time zone.':
    'La hora local de envío utiliza la zona horaria del perfil de cada persona destinataria.',
  'Administrator summaries': 'Resúmenes para administradores',
  'These optional summaries go to current organization administrators. Each person can opt out in their notification preferences.':
    'Estos resúmenes opcionales se envían a las personas administradoras actuales de la organización. Cada persona puede desactivarlos en sus preferencias de notificaciones.',
  'Choose one valid schedule for each administrator cadence.':
    'Elige un horario válido por cada frecuencia de resumen para administradores.',
  Daily: 'Diario',
  Weekly: 'Semanal',
  Monthly: 'Mensual',
  'Enable separate schedules for current organization administrators. Each administrator can turn these optional summaries off in their own preferences.':
    'Configura horarios independientes para las personas administradoras actuales de la organización. Cada una puede desactivar estos resúmenes opcionales en sus preferencias.',
  'Administrator summaries contain current authorized activity counts. Required security notices follow their own policy.':
    'Los resúmenes para administradores contienen cifras de actividad autorizadas actualmente. Los avisos de seguridad obligatorios siguen su propia política.',
};
