// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export const PLATFORM_HEALTH_SPANISH: Readonly<Record<string, string>> = {
  'Platform health': 'Salud de la plataforma',
  'Review service checks and find the next step when something needs attention.':
    'Revisa las comprobaciones de los servicios y los pasos sugeridos cuando algo necesita atención.',
  'Refresh observations': 'Actualizar observaciones',
  'Current organization administrator access is required.':
    'Necesitas acceso vigente de administrador de esta organización.',
  'Platform reports': 'Informes de la plataforma',
  Health: 'Salud',
  'System information': 'Información del sistema',
  'Platform health could not be loaded.': 'No se ha podido cargar la salud de la plataforma.',
  'System information could not be loaded.': 'No se ha podido cargar la información del sistema.',
  'Loading platform health': 'Cargando la salud de la plataforma',
  'Loading system information': 'Cargando la información del sistema',
  'Configuration describes setup. Only current observations can confirm a check passed.':
    'La configuración describe lo que está preparado. Solo las observaciones vigentes confirman una comprobación satisfactoria.',
  'Report checked': 'Informe comprobado',
  'Returned checks': 'Comprobaciones del informe',
  'Needs attention': 'Requiere atención',
  'Not checked or expired': 'Sin comprobar o caducado',
  'Checks passed': 'Comprobaciones satisfactorias',
  'Not enabled': 'Sin activar',
  'Not checked': 'Sin comprobar',
  'Observation expired': 'Observación caducada',
  'Checked sample passed': 'Muestra comprobada satisfactoriamente',
  'Service checks': 'Comprobaciones de servicios',
  'Show checks': 'Mostrar comprobaciones',
  'All checks': 'Todas las comprobaciones',
  Configured: 'Configurado',
  'Not configured': 'Sin configurar',
  'Service check': 'Comprobación de servicio',
  'No checks match this filter.': 'Ninguna comprobación coincide con este filtro.',
  'Check details': 'Detalle de la comprobación',
  Evidence: 'Evidencia',
  'Observed check': 'Comprobación observada',
  'Configuration only': 'Solo configuración',
  'Not observed': 'Sin observar',
  Coverage: 'Cobertura',
  'Complete checked scope': 'Ámbito comprobado completo',
  'Partial coverage': 'Cobertura parcial',
  'Last observed': 'Última observación',
  'Valid until': 'Válido hasta',
  'Not reported': 'No informado',
  'Observed records': 'Registros observados',
  'These counts describe the returned sample, not organization totals.':
    'Estas cifras describen la muestra devuelta, no los totales de la organización.',
  'Records checked': 'Registros comprobados',
  Ready: 'Listo',
  Pending: 'Pendiente',
  Running: 'En curso',
  Failed: 'Fallidos',
  'Suggested next step': 'Siguiente paso sugerido',
  'Review settings': 'Revisar configuración',
  'Installed components and configured limits for the responding process.':
    'Componentes instalados y límites configurados del proceso que responde.',
  'Product and build': 'Producto y compilación',
  Product: 'Producto',
  'Process role': 'Función del proceso',
  'API process': 'Proceso de API',
  'Worker process': 'Proceso de trabajo en segundo plano',
  'Verified build revision': 'Revisión verificada de la compilación',
  License: 'Licencia',
  'Installed components': 'Componentes instalados',
  Component: 'Componente',
  'Configured capabilities': 'Capacidades configuradas',
  'Enabled settings do not confirm external connectivity or running workers.':
    'Una función activada no confirma la conectividad externa ni la ejecución de procesos de trabajo.',
  Enabled: 'Activado',
  Disabled: 'Desactivado',
  'Configured limits': 'Límites configurados',
  'These are configured processing bounds, not measured capacity or replica counts.':
    'Son límites de procesamiento configurados, no mediciones de capacidad ni del número de réplicas.',
  'Processing limit': 'Límite de procesamiento',
  'Per file': 'Por archivo',
  'Per process': 'Por proceso',
  'knowledge spaces': 'espacios de conocimiento',
  Limits: 'Límites',
  'License artifacts': 'Archivos legales y de procedencia',
  'Presence and checksums are reported from installed artifacts. Unknown means provenance is not available.':
    'La presencia y las sumas de verificación se obtienen de los archivos instalados. Desconocido indica que no se dispone de su procedencia.',
  'Attribution notice': 'Aviso de atribución',
  'Software bill of materials': 'Inventario de componentes de software',
  Included: 'Incluido',
  'Not provided': 'No incluido',
  Unknown: 'Desconocido',
  'No artifact observations were returned.':
    'No se han devuelto observaciones de archivos legales.',
  'Catalog database': 'Base de datos del catálogo',
  'Document database': 'Base de datos de documentos',
  'Document database access policy': 'Política de acceso a la base de datos de documentos',
  'Dataset database': 'Base de datos de conjuntos de datos',
  'Dataset database access policy': 'Política de acceso a la base de datos de datasets',
  'Document file storage': 'Almacenamiento de documentos',
  'Dataset file storage': 'Almacenamiento de datasets',
  'Document search indexes': 'Índices de búsqueda de documentos',
  'Dataset search indexes': 'Índices de búsqueda de datasets',
  'Document ingestion': 'Ingesta de documentos',
  'Dataset ingestion': 'Ingesta de datasets',
  'Knowledge model configuration': 'Configuración de modelos de conocimiento',
  'Email communications': 'Comunicaciones por correo',
  'Background workers': 'Procesos en segundo plano',
  'The database responded to a bounded connectivity check.':
    'La base de datos respondió a una comprobación acotada de conectividad.',
  'The database could not complete its connectivity check.':
    'La base de datos no pudo completar la comprobación de conectividad.',
  'The runtime database access policy has not been verified.':
    'No se ha verificado la política de acceso de la base de datos en ejecución.',
  'The runtime database role does not meet the required access policy.':
    'El rol de ejecución de la base de datos no cumple la política de acceso requerida.',
  'This knowledge service is disabled in configuration.':
    'Este servicio de conocimiento está desactivado en la configuración.',
  'File storage is configured. This report does not test reading or writing files.':
    'El almacenamiento está configurado. Este informe no prueba la lectura ni la escritura de archivos.',
  'The returned search index checks passed.':
    'Las comprobaciones devueltas de los índices de búsqueda han sido satisfactorias.',
  'Some checked search indexes need attention.':
    'Algunos de los índices de búsqueda comprobados necesitan atención.',
  'Search index readiness has not been observed.':
    'No se ha observado si los índices de búsqueda están preparados.',
  'No search indexes were found in the checked scope.':
    'No se encontraron índices de búsqueda en el ámbito comprobado.',
  'The report contains a bounded observation of processing records.':
    'El informe contiene una observación acotada de los registros de procesamiento.',
  'Some observed processing records contain failures.':
    'Algunos registros de procesamiento observados contienen errores.',
  'Model assignments are configured. Generation and connectivity have not been tested here.':
    'Las asignaciones de modelos están configuradas. Aquí no se han probado la generación ni la conectividad.',
  'Required knowledge model assignments are missing or incomplete.':
    'Faltan asignaciones de modelos de conocimiento requeridas o están incompletas.',
  'The provider has not been tested by this report.': 'Este informe no ha probado el proveedor.',
  'Email communications are disabled in configuration.':
    'Las comunicaciones por correo están desactivadas en la configuración.',
  'Email communications are configured. Delivery has not been tested here.':
    'Las comunicaciones por correo están configuradas. Aquí no se ha probado la entrega.',
  'Email communications need additional configuration.':
    'Las comunicaciones por correo necesitan configuración adicional.',
  'No current worker heartbeat is available. Processing configuration does not confirm a running worker.':
    'No hay una señal de actividad vigente de los procesos de trabajo. La configuración de procesamiento no confirma que estén ejecutándose.',
  'A current observation is unavailable.': 'No se dispone de una observación vigente.',
  'This observation covers a limited sample. It does not describe every resource.':
    'Esta observación abarca una muestra limitada. No describe todos los recursos.',
  'This observation has expired. Refresh to request the latest available checks.':
    'Esta observación ha caducado. Actualiza para solicitar las últimas comprobaciones disponibles.',
  'No action is suggested by this check.': 'Esta comprobación no sugiere ninguna acción.',
  'Refresh observations to request the latest available checks.':
    'Actualiza las observaciones para solicitar las últimas comprobaciones disponibles.',
  'Review the affected service configuration with your deployment administrator.':
    'Revisa la configuración del servicio afectado con el administrador de la instalación.',
  'Review search index assignments and indexing activity for the affected knowledge spaces.':
    'Revisa las asignaciones de índices y la actividad de indexación de los espacios de conocimiento afectados.',
  'Review processing activity and the source files associated with failed records.':
    'Revisa la actividad de procesamiento y los archivos de origen asociados a los registros fallidos.',
  'Review the email provider and communications policy. This report does not send a test email.':
    'Revisa el proveedor de correo y la política de comunicaciones. Este informe no envía correos de prueba.',
  'Ask your deployment administrator to check worker execution and observation collection.':
    'Pide al administrador de la instalación que compruebe la ejecución de los procesos de trabajo y la recogida de observaciones.',
  'koinon application': 'Aplicación koinon',
  'Document knowledge': 'Conocimiento documental',
  'Structured knowledge': 'Conocimiento estructurado',
  'File storage': 'Almacenamiento de archivos',
  'Python SDK': 'SDK de Python',
  'pyfly framework': 'Framework pyfly',
  'API operation capacity': 'Capacidad de operaciones de API',
  'Worker operation capacity': 'Capacidad de operaciones de trabajo',
  'Worker concurrency': 'Concurrencia de los procesos de trabajo',
  'Knowledge spaces per index check': 'Espacios por comprobación de índices',
  'MCP request concurrency': 'Concurrencia de solicitudes MCP',
  'MCP request limit': 'Límite de solicitudes MCP',
  'MCP response limit': 'Límite de respuestas MCP',
  'Source file size limit': 'Límite de tamaño del archivo de origen',
  'Processing scratch space limit': 'Límite del espacio temporal de procesamiento',
  'Document process memory limit': 'Límite de memoria del proceso de documentos',
  'Knowledge services': 'Servicios de conocimiento',
  'MCP connections': 'Conexiones MCP',
  'Scheduled processing': 'Procesamiento programado',
};
