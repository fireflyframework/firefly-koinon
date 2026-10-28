// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export const KNOWLEDGE_SPANISH: Readonly<Record<string, string>> = {
  'Settings could not be loaded.': 'No se pudo cargar la configuración.',
  'Sources could not be loaded.': 'No se pudieron cargar las fuentes.',

  'Model options': 'Opciones del modelo',
  'Choose a provider.': 'Elige un proveedor.',
  'Choose a model.': 'Elige un modelo.',
  'Not reported': 'No informado',
  'Knowledge models': 'Modelos de conocimiento',
  'Choose the models used to process, search and answer questions about your knowledge.':
    'Elige los modelos para procesar y buscar conocimiento y responder preguntas.',
  'Assignment scope': 'Ámbito de la asignación',
  'Organization default': 'Valor predeterminado de la organización',
  'Workspace override': 'Excepción del espacio',
  'Workspace overrides take precedence over organization defaults.':
    'Las excepciones del espacio tienen prioridad sobre los valores de la organización.',
  'These defaults apply to workspaces without an override.':
    'Estos valores se aplican a los espacios que no tienen una excepción.',
  'Knowledge models could not be loaded. Try again.':
    'No se pudieron cargar los modelos de conocimiento. Inténtalo de nuevo.',
  'Knowledge models could not be loaded.': 'No se pudieron cargar los modelos de conocimiento.',
  'Error details': 'Detalles del error',
  'Reload assignments': 'Volver a cargar las asignaciones',
  'Back to assignments': 'Volver a las asignaciones',
  'Model selection': 'Selección del modelo',
  'Choose a provider and model': 'Elegir un proveedor y un modelo',
  'Use the current chat agent': 'Usar el agente del chat actual',
  'This choice works only during a chat run. Operations outside Chat need a separate model assignment.':
    'Esta opción solo funciona durante una ejecución de chat. Las operaciones fuera de Chat necesitan una asignación de modelo independiente.',
  'Connect a compatible provider in Providers before assigning this role.':
    'Conecta un proveedor compatible en Proveedores antes de asignar esta función.',
  'An existing compatible index is required': 'Se necesita un índice compatible existente',
  'Ask your deployment administrator for the approved index reference and dimensions. Saving an assignment does not build or migrate an index.':
    'Pide al administrador de la instalación la referencia y las dimensiones del índice aprobado. Guardar una asignación no crea ni migra un índice.',
  'Model dimensions': 'Dimensiones del modelo',
  'Storage dimensions': 'Dimensiones de almacenamiento',
  'Document model and storage dimensions must match.':
    'Las dimensiones del modelo de documentos y del almacenamiento deben coincidir.',
  'Dataset indexes require 1536 storage dimensions.':
    'Los índices de datos necesitan 1536 dimensiones de almacenamiento.',
  'Approved index reference': 'Referencia del índice aprobado',
  'Changing an embedding model, dimensions or index may require a reviewed reindex. Removing and recreating an assignment does not bypass this requirement.':
    'Cambiar el modelo de embeddings, las dimensiones o el índice puede requerir una reindexación revisada. Eliminar y volver a crear una asignación no evita este requisito.',
  'Enable this assignment': 'Activar esta asignación',
  'A disabled workspace override blocks the organization default for this role.':
    'Una excepción desactivada del espacio impide usar el valor predeterminado de la organización para esta función.',
  'Saving records your choice. Availability and index compatibility are checked when a knowledge operation runs.':
    'Guardar registra tu selección. La disponibilidad y la compatibilidad del índice se comprueban al ejecutar una operación de conocimiento.',
  'Save assignment': 'Guardar asignación',
  'Remove assignment': 'Eliminar asignación',
  'Remove workspace override': 'Eliminar excepción del espacio',
  'Remove this override and use the organization default, if one is assigned?':
    '¿Eliminar esta excepción y usar el valor predeterminado de la organización, si existe?',
  'Remove this organization assignment? Knowledge operations using this role may stop until another assignment is added.':
    '¿Eliminar esta asignación de la organización? Las operaciones de conocimiento que usen esta función pueden dejar de funcionar hasta que se añada otra asignación.',
  'Keep assignment': 'Conservar asignación',
  'Assigned models have not been tested by this screen. Run a knowledge operation to check availability and index compatibility.':
    'Esta pantalla no ha probado los modelos asignados. Ejecuta una operación de conocimiento para comprobar su disponibilidad y la compatibilidad del índice.',
  'Uses organization default': 'Usa el valor predeterminado de la organización',
  'No model assigned': 'Sin modelo asignado',
  'Current chat agent': 'Agente del chat actual',
  'Model unavailable': 'Modelo no disponible',
  'Provider unavailable': 'Proveedor no disponible',
  Assigned: 'Asignado',
  'Not assigned': 'Sin asignar',
  'No assignment': 'Sin asignación',
  Configure: 'Configurar',
  Customize: 'Personalizar',
  'No knowledge model roles are available in this deployment.':
    'Esta instalación no ofrece funciones de modelos de conocimiento.',
  'Choose a separate provider for this role.':
    'Elige un proveedor independiente para esta función.',
  'Choose a provider and model available in this organization.':
    'Elige un proveedor y un modelo disponibles en esta organización.',
  'Enter a whole number from 1 to 4096.': 'Introduce un número entero entre 1 y 4096.',
  'Enter the approved reference for an existing compatible index.':
    'Introduce la referencia aprobada de un índice compatible existente.',
  'The index reference must contain at most 256 characters.':
    'La referencia del índice puede contener como máximo 256 caracteres.',
  'Model dimensions cannot exceed storage dimensions.':
    'Las dimensiones del modelo no pueden superar las dimensiones de almacenamiento.',
  'Knowledge model assignment saved.': 'Asignación de modelo de conocimiento guardada.',
  'Workspace override removed.': 'Excepción del espacio eliminada.',
  'Knowledge model assignment removed.': 'Asignación de modelo de conocimiento eliminada.',
  'Another operator changed this assignment. Reload it before saving again.':
    'Otro operador ha cambiado esta asignación. Vuelve a cargarla antes de guardar.',
  'This role already has an assignment. Reload to edit its current version.':
    'Esta función ya tiene una asignación. Vuelve a cargarla para editar su versión actual.',
  'This index is tied to a different embedding configuration. Ask your deployment administrator to complete a reviewed reindex before changing it.':
    'Este índice está vinculado a otra configuración de embeddings. Pide al administrador de la instalación que complete una reindexación revisada antes de cambiarlo.',
  'This role needs a running chat agent. Choose a separate provider for operations outside Chat.':
    'Esta función necesita un agente de chat en ejecución. Elige un proveedor independiente para las operaciones fuera de Chat.',
  'Check the approved index reference and its model and storage dimensions.':
    'Comprueba la referencia del índice aprobado y las dimensiones de su modelo y almacenamiento.',
  'The organization, workspace and role cannot be changed on an existing assignment.':
    'La organización, el espacio y la función no se pueden cambiar en una asignación existente.',
  'You do not have permission in this scope. Choose an authorized workspace or contact an administrator.':
    'No tienes permiso en este ámbito. Elige un espacio autorizado o contacta con un administrador.',
  'Document answer and query expansion': 'Respuestas sobre documentos y ampliación de consultas',
  'Explicit document answer fallback': 'Modelo alternativo para respuestas sobre documentos',
  'Document consolidation': 'Consolidación de documentos',
  'Document evidence tools': 'Herramientas de evidencia de documentos',
  'Structured question grounding': 'Contexto de preguntas sobre datos',
  'SQL generation': 'Generación de SQL',
  'SQL repair': 'Corrección de SQL',
  'Result explanation': 'Explicación de resultados',
  'Schema descriptions and names': 'Descripciones y nombres de esquemas',
  'Relation proposals': 'Propuestas de relaciones',
  'Schema rename detection': 'Detección de cambios de nombre en esquemas',
  'Structured schema embeddings': 'Embeddings de esquemas de datos',
  'Query complete': 'Consulta completada',
  'Query failed': 'La consulta ha fallado',
  'Blocked by query policy': 'Bloqueada por la política de consultas',
  'Status unavailable': 'Estado no disponible',
  'Deployment connections are managed by your administrator. Use Knowledge models to assign providers to knowledge roles.':
    'El administrador gestiona las conexiones de la instalación. Usa Modelos de conocimiento para asignar proveedores a las funciones de conocimiento.',
};
