// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export const MCP_APPLICATIONS_SPANISH: Readonly<Record<string, string>> = {
  Applications: 'Aplicaciones',
  'Application filters': 'Filtros de aplicaciones',
  'Organization applications': 'Aplicaciones de la organización',
  'Register the applications your organization can connect to koinon.':
    'Registra las aplicaciones que tu organización puede conectar a koinon.',
  'Register application': 'Registrar aplicación',
  'Edit application': 'Editar aplicación',
  'Manage application': 'Gestionar aplicación',
  'Reload applications': 'Recargar aplicaciones',
  'Deployment setup required': 'Requiere configuración del despliegue',
  'A deployment administrator must complete these settings before applications can connect.':
    'Un administrador del despliegue debe completar estos ajustes antes de conectar aplicaciones.',
  'Enable the MCP endpoint.': 'Habilita el endpoint MCP.',
  'Enable OAuth connections.': 'Habilita las conexiones OAuth.',
  'Configure an OAuth encryption key.': 'Configura una clave de cifrado OAuth.',
  'Save this client secret': 'Guarda este secreto de cliente',
  'It is shown only in this view. Store it securely before you close it.':
    'Solo se muestra en esta vista. Guárdalo en un lugar seguro antes de cerrarla.',
  'Client ID': 'ID de cliente',
  'Client secret': 'Secreto de cliente',
  'Hide secret': 'Ocultar secreto',
  'Reveal secret': 'Mostrar secreto',
  'Copy secret': 'Copiar secreto',
  'I saved the secret': 'He guardado el secreto',
  'Secret copied. Store it securely before closing this view.':
    'Secreto copiado. Guárdalo en un lugar seguro antes de cerrar esta vista.',
  'The secret could not be copied. Reveal it and copy it manually.':
    'No se pudo copiar el secreto. Muéstralo y cópialo manualmente.',
  'Close application editor': 'Cerrar el editor de aplicaciones',
  'Applications receive only the access their users approve. Organization permissions still apply.':
    'Las aplicaciones solo reciben el acceso que aprueban sus usuarios. Los permisos de la organización siguen aplicándose.',
  'Application setup steps': 'Pasos de configuración de la aplicación',
  'Application details': 'Datos de la aplicación',
  'Allowed access': 'Acceso permitido',
  'Review application': 'Revisar aplicación',
  'Application name': 'Nombre de la aplicación',
  'Use a name people will recognize when they connect.':
    'Usa un nombre que las personas reconozcan al conectarse.',
  'Application type': 'Tipo de aplicación',
  'Public application': 'Aplicación pública',
  'Confidential application': 'Aplicación confidencial',
  Public: 'Pública',
  Confidential: 'Confidencial',
  'Desktop or browser applications that cannot safely store a secret. Uses PKCE.':
    'Aplicaciones de escritorio o navegador que no pueden guardar un secreto de forma segura. Usa PKCE.',
  'A server application that can securely store a client secret. Uses PKCE and a secret.':
    'Una aplicación de servidor que puede guardar un secreto de cliente de forma segura. Usa PKCE y un secreto.',
  'Callback URLs': 'URLs de retorno',
  'callback URLs': 'URLs de retorno',
  'callback URL': 'URL de retorno',
  'Paste the exact callback URLs provided by the application, one per line. Up to eight URLs.':
    'Pega las URLs de retorno exactas que proporciona la aplicación, una por línea. Hasta ocho URLs.',
  'Enter between one and eight callback URLs, one per line.':
    'Introduce entre una y ocho URLs de retorno, una por línea.',
  'Each callback URL must be distinct.': 'Las URLs de retorno no pueden repetirse.',
  'Use exact HTTPS callback URLs without wildcards, credentials or fragments. HTTP is allowed only for local development.':
    'Usa URLs HTTPS exactas, sin comodines, credenciales ni fragmentos. HTTP solo se permite para desarrollo local.',
  'Enter an application name of up to 120 characters.':
    'Introduce un nombre de aplicación de hasta 120 caracteres.',
  'Application enabled': 'Aplicación habilitada',
  'Choose the maximum access this application may request. Users approve their own connection separately.':
    'Elige el acceso máximo que puede solicitar la aplicación. Cada usuario aprueba su conexión por separado.',
  'Browse knowledge': 'Consultar el conocimiento',
  'Find folders, files and datasets. Required for every application.':
    'Consulta carpetas, archivos y datasets. Es obligatorio para todas las aplicaciones.',
  'Search knowledge': 'Buscar conocimiento',
  'Search the organization’s permitted knowledge.':
    'Busca en el conocimiento de la organización al que tienes acceso.',
  'Query datasets': 'Consultar datos',
  'Ask questions about structured data.': 'Realiza consultas sobre datos estructurados.',
  'Inspect saved answers': 'Inspeccionar respuestas guardadas',
  'Inspect existing answer audits when Read answer evidence is also allowed.':
    'Consulta las auditorías de respuestas existentes si también se permite Consultar evidencias de las respuestas.',
  'Read answer evidence': 'Consultar evidencias de las respuestas',
  'Inspect sources and the execution audit.': 'Consulta las fuentes y la auditoría de ejecución.',
  'Maintain knowledge': 'Mantener el conocimiento',
  'Propose changes for human review in a compatible chat application.':
    'Propón cambios para su revisión humana en una aplicación de chat compatible.',
  'Upload files': 'Subir archivos',
  'Upload files after human review. Includes Maintain knowledge.':
    'Sube archivos tras su revisión humana. Incluye Mantener conocimiento.',
  'Saving changes revokes all existing connections to this application. Users must connect again.':
    'Guardar los cambios revoca todas las conexiones existentes a esta aplicación. Los usuarios deberán volver a conectarse.',
  'I reviewed the callbacks and allowed access.':
    'He revisado las URLs de retorno y el acceso permitido.',
  'I reviewed these changes and understand that existing connections will be revoked.':
    'He revisado los cambios y entiendo que se revocarán las conexiones existentes.',
  'Search applications': 'Buscar aplicaciones',
  'Name or client ID': 'Nombre o ID de cliente',
  'Apply application filter': 'Aplicar filtro de aplicaciones',
  'All applications': 'Todas las aplicaciones',
  Enabled: 'Activado',
  Disabled: 'Desactivado',
  'Sort by': 'Ordenar por',
  'Last updated': 'Última actualización',
  Order: 'Orden',
  Ascending: 'Ascendente',
  Descending: 'Descendente',
  Application: 'Aplicación',
  'Loading applications': 'Cargando aplicaciones',
  'Refresh the application list': 'Actualiza la lista de aplicaciones',
  'No matching applications': 'No hay aplicaciones coincidentes',
  'No registered applications': 'No hay aplicaciones registradas',
  'Retrieving the current organization applications.':
    'Consultando las aplicaciones actuales de la organización.',
  'Reload to see the current applications after your changes.':
    'Recarga la lista para ver las aplicaciones tras los cambios.',
  'Try another name, client ID or status.': 'Prueba con otro nombre, ID de cliente o estado.',
  'Register an application to let people connect it to this organization.':
    'Registra una aplicación para que las personas puedan conectarla a esta organización.',
  'Loading application details': 'Cargando datos de la aplicación',
  'Application registration': 'Registro de aplicación',
  'Close application details': 'Cerrar los datos de la aplicación',
  'Disable application': 'Deshabilitar aplicación',
  'Rotate client secret': 'Renovar secreto de cliente',
  'Disable this application?': '¿Deshabilitar esta aplicación?',
  'Replace this client secret?': '¿Sustituir este secreto de cliente?',
  'All existing connections to this application will be revoked. Users must connect again.':
    'Se revocarán todas las conexiones existentes a esta aplicación. Los usuarios deberán volver a conectarse.',
  'The old secret stops working immediately. Update the application with the new secret.':
    'El secreto anterior dejará de funcionar de inmediato. Configura el nuevo secreto en la aplicación.',
  'I understand that existing connections will be revoked.':
    'Entiendo que se revocarán las conexiones existentes.',
  'Deployment-configured applications remain read-only and are managed by your deployment administrator.':
    'Las aplicaciones configuradas en el despliegue son de solo lectura y las gestiona su administrador.',
  'Application setup could not be checked. Try again.':
    'No se pudo comprobar la configuración de las aplicaciones. Inténtalo de nuevo.',
  'Applications could not be loaded. Try again.':
    'No se pudieron cargar las aplicaciones. Inténtalo de nuevo.',
  'This application could not be opened. Try again.':
    'No se pudo abrir esta aplicación. Inténtalo de nuevo.',
  'Application created. Copy its secret now if one was issued. It cannot be shown again.':
    'Aplicación creada. Si se ha generado un secreto, cópialo ahora. No podrá volver a mostrarse.',
  'Application updated. Existing connections have been revoked. Users must connect again.':
    'Aplicación actualizada. Las conexiones existentes se han revocado. Los usuarios deberán volver a conectarse.',
  'This application changed. Reload before making another change.':
    'La aplicación ha cambiado. Recarga los datos antes de modificarla.',
  'The result could not be confirmed. Reload to check the application before trying again. A secret from a lost response cannot be recovered.':
    'No se pudo confirmar el resultado. Recarga los datos para comprobar la aplicación antes de repetir la operación. No se puede recuperar un secreto cuya respuesta se haya perdido.',
  'The application could not be changed. Review your access and application settings.':
    'No se pudo modificar la aplicación. Revisa tu acceso y su configuración.',
};
