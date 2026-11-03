// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export const KNOWLEDGE_BEHAVIOR_SPANISH: Readonly<Record<string, string>> = {
  'Index activation receipts': 'Recibos de activación de índices',
  'Each receipt retains the admitted workspace and index version, including earlier activations of a reused index.':
    'Cada recibo conserva el espacio y la versión de índice admitidos, incluidas las activaciones anteriores de un índice reutilizado.',
  'Index version:': 'Versión del índice:',
  'Workspace:': 'Espacio:',
  'Receipt:': 'Recibo:',
  'Load more activation receipts': 'Cargar más recibos de activación',
  'Recovery pagination did not advance. Refresh the status.': 'La paginación de recuperación no avanzó. Actualiza el estado.',
  pending: 'pendiente',
  finished: 'Finalizado',
  restored: 'Restaurado',
  aborted: 'Interrumpido',
  'Mode preparation': 'Preparación del modo',
  'Active mode:': 'Modo activo:',
  'Requested mode:': 'Modo solicitado:',
  'Prepare mode change': 'Preparar cambio de modo',
  'Refresh preparation': 'Actualizar preparación',
  'Discovering documents': 'Buscando documentos',
  'Checking model assignments': 'Comprobando modelos asignados',
  'Preparing document views': 'Preparando vistas de documentos',
  'Preparing document indexes': 'Preparando índices de documentos',
  'Verifying current knowledge': 'Verificando el conocimiento actual',
  'Activating requested mode': 'Activando el modo solicitado',
  'Preparation requested. The active mode remains unchanged.':
    'Preparación solicitada. El modo activo no cambia.',
  'Preparation completed. Reload the settings to see the active revision.':
    'Preparación completada. Actualiza la configuración para ver la revisión activa.',
  'The active mode remains unchanged while preparation runs or needs attention.':
    'El modo activo no cambia mientras la preparación está en curso o requiere atención.',
  'Knowledge changed during preparation. Changed workspaces are being checked again.':
    'El conocimiento cambió durante la preparación. Se están verificando de nuevo los espacios modificados.',
  'Catalog entries checked:': 'Entradas del catálogo revisadas:',
  'Verification checks:': 'Comprobaciones de verificación:',
  'Current stage time (ms):': 'Tiempo de la etapa actual (ms):',
  'Processing job:': 'Trabajo de procesamiento:',
  'Worker lease until:': 'Reserva del worker hasta:',
  'Open source': 'Abrir fuente',
  'Inspect index job': 'Inspeccionar trabajo de índice',
  'Index reconciliation is still required. Cancelling a mode change does not undo a native index switch.':
    'El índice sigue pendiente de conciliación. Cancelar el cambio de modo no deshace un cambio nativo de índice.',
  'Review finishing the index activation': 'Revisar finalización de la activación del índice',
  'Review restoring the previous index': 'Revisar restauración del índice anterior',
  'Load more preparation targets': 'Cargar más destinos de preparación',
  'Review index reconciliation': 'Revisar conciliación del índice',
  'Finish only the already-applied index switch. This does not activate a cancelled mode change or repeat embedding calls.':
    'Finaliza únicamente el cambio de índice ya aplicado. No activa un cambio de modo cancelado ni repite llamadas de embeddings.',
  'Restore the recorded previous index. This does not activate a cancelled mode change or repeat embedding calls.':
    'Restaura el índice anterior registrado. No activa un cambio de modo cancelado ni repite llamadas de embeddings.',
  'Confirm index reconciliation': 'Confirmar conciliación del índice',
  'Retry preparation': 'Reintentar preparación',
  'Cancel mode change': 'Cancelar cambio de modo',
  'Inspect the source and job outcome first. Retrying may repeat incomplete model calls and incur usage again.':
    'Revisa primero la fuente y el resultado del trabajo. Reintentar puede repetir llamadas incompletas al modelo y generar consumo adicional.',
  'I reviewed the prerequisites and retry usage':
    'Revisé los requisitos y el consumo del reintento',
  'The request outcome is unknown. Check its status before submitting another change.':
    'Se desconoce el resultado de la solicitud. Consulta su estado antes de enviar otro cambio.',
  'Check the same request': 'Comprobar la misma solicitud',
  'Preparation status could not be loaded. Refresh to try again.':
    'No se pudo cargar el estado de preparación. Actualiza para volver a intentarlo.',
  'Preparation pagination did not advance. Refresh the status.':
    'La paginación de la preparación no avanzó. Actualiza el estado.',
  queued: 'En cola',
  running: 'En curso',
  failed: 'Fallido',
  cancelled: 'Cancelado',
  superseded: 'Sustituido',
  succeeded: 'Completado',
  prepared: 'Preparado',
  ready: 'Listo',
  waiting: 'En espera',
  excluded: 'Fuera del alcance actual',
  workspace: 'Espacio',
  document: 'Documento',
  curated: 'Conocimiento curado',
  'RLM needs document versions with recorded processing details. Older documents may need to be reprocessed.':
    'RLM necesita versiones de documento con el procesamiento registrado. Puede ser necesario volver a procesar los documentos antiguos.',
  'Knowledge behavior': 'Comportamiento del conocimiento',
  'These settings apply to this organization. Workspace model assignments remain separate.':
    'Esta configuración se aplica a esta organización. Las asignaciones de modelos por espacio se mantienen aparte.',
  'Reload knowledge behavior': 'Recargar el comportamiento del conocimiento',
  'Loading knowledge behavior': 'Cargando el comportamiento del conocimiento',
  'Using deployment settings': 'Usa la configuración de la instalación',
  'Saved for this organization': 'Guardado para esta organización',
  Revision: 'Revisión',
  'You can view these settings. An organization administrator with settings permission can change them.':
    'Puedes consultar esta configuración. Un administrador de la organización con permiso de configuración puede modificarla.',
  'Document answers': 'Respuestas de documentos',
  'Choose how koinon uses authorized documents to answer questions.':
    'Elige cómo usa koinon los documentos autorizados para responder preguntas.',
  'Find relevant passages (RAG)': 'Buscar fragmentos relevantes (RAG)',
  'Analyze documents in steps (RLM)': 'Analizar documentos por pasos (RLM)',
  'Find relevant passages and use them to answer.':
    'Busca fragmentos relevantes y los usa para responder.',
  'Examine documents through several analysis steps before answering.':
    'Examina los documentos mediante varios pasos de análisis antes de responder.',
  'RLM uses document files': 'RLM usa archivos de documentos',
  'Curated knowledge requires RAG; koinon will not switch methods automatically.':
    'El conocimiento curado requiere RAG; koinon no cambiará de método automáticamente.',
  'Document search and answers': 'Búsqueda y respuestas sobre documentos',
  'Control how document passages are found and used to answer.':
    'Controla cómo se buscan los fragmentos de documentos y cómo se usan para responder.',
  'Document analysis': 'Análisis de documentos',
  'More analysis steps, calls or independent attempts can increase response time and model usage.':
    'Más pasos, llamadas o intentos independientes de análisis pueden aumentar el tiempo de respuesta y el uso del modelo.',
  'Dataset queries': 'Consultas de datos',
  'Dataset questions use schema context and SQL generation, review and explanation.':
    'Las preguntas sobre datos usan contexto de esquemas y generación, revisión y explicación de SQL.',
  'Retrieved passages': 'Fragmentos recuperados',
  'Candidates per search': 'Candidatos por búsqueda',
  'Search fusion constant': 'Constante de fusión de búsquedas',
  'Expand search queries': 'Ampliar las consultas de búsqueda',
  'Expanded queries': 'Consultas ampliadas',
  'Passages used to answer': 'Fragmentos usados para responder',
  'Analysis steps': 'Pasos de análisis',
  'Analysis calls': 'Llamadas de análisis',
  'Analysis depth': 'Profundidad del análisis',
  'Independent analysis attempts': 'Intentos independientes de análisis',
  'Extended reasoning': 'Razonamiento ampliado',
  'Schema matches': 'Coincidencias de esquemas',
  'Query examples': 'Ejemplos de consultas',
  'Metric matches': 'Coincidencias de métricas',
  'Schema fusion constant': 'Constante de fusión de esquemas',
  'Query candidates': 'Consultas candidatas',
  'Query repair attempts': 'Intentos de corrección de consultas',
  'Minimum grounding confidence': 'Confianza mínima del contexto',
  'Limits unavailable': 'Límites no disponibles',
  'Model prerequisites': 'Requisitos de modelos',
  'Assignments are checked when an operation runs. Assigned does not mean runtime availability has been verified.':
    'Las asignaciones se comprueban al ejecutar una operación. Una asignación no implica que se haya verificado la disponibilidad en ejecución.',
  'Model assignments could not be read in this scope. An administrator can review them in Knowledge models.':
    'No se pudieron consultar las asignaciones de modelos en este ámbito. Un administrador puede revisarlas en Modelos de conocimiento.',
  'Review model assignments': 'Revisar las asignaciones de modelos',
  'Save changes': 'Guardar cambios',
  'Knowledge behavior saved.': 'Comportamiento del conocimiento guardado.',
  'Knowledge behavior changed. Reload the settings before saving again.':
    'El comportamiento del conocimiento ha cambiado. Recarga la configuración antes de volver a guardar.',
  'Knowledge behavior could not be loaded. Try again.':
    'No se pudo cargar el comportamiento del conocimiento. Inténtalo de nuevo.',
  'Choose an available document answer method.':
    'Elige un método de respuesta sobre documentos disponible.',
  'Enter a number within the displayed limits.':
    'Introduce un número dentro de los límites indicados.',
  'Enter a whole number within the displayed limits.':
    'Introduce un número entero dentro de los límites indicados.',
};
