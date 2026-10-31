// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export const ORGANIZATION_CHAT_SPANISH: Readonly<Record<string, string>> = {
  'Conversation memory': 'Memoria de conversaciones',
  'Set the maximum context available to chat. People still choose whether to enable memory in each folder.':
    'Define el contexto máximo del chat. Cada persona decide si activa la memoria en sus carpetas.',
  'Allow personal project memory': 'Permitir memoria personal por proyecto',
  'Only the owner’s chats with the same knowledge scope can contribute. Private files stay in their original chat.':
    'Solo aportan contexto los chats de su propietario con el mismo ámbito de conocimiento. Los archivos privados permanecen en su chat original.',
  'Total history messages': 'Mensajes totales del historial',
  'Messages from other project chats': 'Mensajes de otros chats del proyecto',
  'History token budget': 'Límite de tokens del historial',
  'Project messages count toward the total. Zero disables that part of the context. Deployment limits also apply.':
    'Los mensajes del proyecto cuentan dentro del total. El valor cero desactiva esa parte del contexto. También se aplican los límites de la instalación.',
  'Memory provides conversation context. Answers about organizational knowledge still require current, authorized sources.':
    'La memoria aporta contexto a la conversación. Las respuestas sobre el conocimiento de la organización requieren fuentes vigentes y autorizadas.',
  'Enter whole numbers within the memory limits.':
    'Introduce números enteros dentro de los límites de memoria.',
  'Project memory cannot exceed the total history limit.':
    'La memoria del proyecto no puede superar el límite total del historial.',
  'Organization chat': 'Chat de la organización',
  'Choose once for this organization. Everyone uses this agent in chat.':
    'Elige una vez para esta organización. Todas las personas usan este agente en el chat.',
  'Reload organization chat': 'Recargar el chat de la organización',
  'Organization chat agent': 'Agente del chat de la organización',
  'No agent — chat unavailable': 'Sin agente — chat no disponible',
  'Unavailable agent': 'Agente no disponible',
  'Save organization chat': 'Guardar el chat de la organización',
  'Organization chat saved.': 'Chat de la organización guardado.',
  'Organization chat settings could not be loaded.':
    'No se pudo cargar la configuración del chat de la organización.',
  'Organization chat changed. Reload the settings before saving again.':
    'El chat de la organización ha cambiado. Recarga la configuración antes de volver a guardar.',
  'The selected agent is unavailable for chat. Review its configuration or choose another organization agent.':
    'El agente seleccionado no está disponible para el chat. Revisa su configuración o elige otro agente de la organización.',
  'Chat is unavailable until an organization agent is selected.':
    'El chat no estará disponible hasta que se seleccione un agente de la organización.',
};
