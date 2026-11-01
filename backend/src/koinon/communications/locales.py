# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Notification locale is explicit; an automatic profile default is never preference evidence."""

import re
from typing import Literal

LocaleOrigin = Literal["user", "organization", "installation", "default"]


def normalize_locale(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:en|es)(?:-[A-Za-z0-9]{2,8}){0,4}", value, re.IGNORECASE
    ):
        raise ValueError("Choose a supported English or Spanish notification locale")
    parts = value.split("-")
    return "-".join(
        [
            parts[0].lower(),
            *(
                part.upper() if len(part) == 2 else part.title() if len(part) == 4 else part
                for part in parts[1:]
            ),
        ]
    )


def effective_locale(*, user=None, organization=None, installation=None) -> tuple[str, LocaleOrigin]:
    choices: tuple[tuple[str | None, LocaleOrigin], ...] = (
        (user, "user"),
        (organization, "organization"),
        (installation, "installation"),
    )
    for value, origin in choices:
        if value is not None:
            return normalize_locale(value), origin
    return "en-US", "default"


_COPY = {
    "en": {
        "security_delivery_diagnostic_subject": "{product}: email delivery diagnostic for {scope}",
        "security_delivery_diagnostic": (
            "Your deployment operator requested this new email delivery diagnostic "
            "for your approved account. "
            "No credentials or private content are included."
        ),
        "diagnostic_title": "Email delivery diagnostic",
        "diagnostic_footer": (
            "This diagnostic was requested by your deployment operator. "
            "Receiving it does not change your access or retry a previous message."
        ),
        "security_token_created_subject": "{product}: API token created in {scope}",
        "security_token_revoked_subject": "{product}: API token revoked in {scope}",
        "security_application_granted_subject": "{product}: application connected in {scope}",
        "security_application_revoked_subject": "{product}: application disconnected in {scope}",
        "security_client_registered_subject": "{product}: OAuth client registered in {scope}",
        "security_client_revoked_subject": "{product}: OAuth client revoked in {scope}",
        "security_client_secret_rotated_subject": "{product}: OAuth client secret rotated in {scope}",
        "security_client_changed_subject": "{product}: OAuth client settings changed in {scope}",
        "invite_subject": "{product}: your invitation to {scope}",
        "invite_heading": "You're invited to collaborate",
        "invite_by": "{actor} invited you to collaborate in {organization}.",
        "team_fallback": "The {organization} team",
        "invite_action": "Review invitation",
        "invite_footer": (
            "This invitation is bound to your corporate account. Forwarding the link does "
            "not grant access to another person."
        ),
        "invite_sign_in": (
            "Sign in with your corporate account to review the proposed access. Accept or "
            "decline before any permission is granted."
        ),
        "invite_scope": "Proposed access: {scope}, {role} role assignment.",
        "invite_expiry": "This invitation expires on {expiry}.",
        "administrative_digest_heading": "Organization activity summary",
        "administrative_digest_subject": "{product}: {cadence} organization activity summary for {scope}",
        "administrative_digest_description": (
            "Knowledge created, updated and consulted across your organization's "
            "currently accessible projects."
        ),
        "project_total": "{count} activities",
        "project_created": "Created",
        "project_updated": "Updated",
        "project_consulted": "Consulted",
        "project_counts_description": (
            "Recorded activity combines created, updated and consulted counts. "
            "A piece may appear in more than one category."
        ),
        "digest_heading": "Your activity summary",
        "digest_subject": "{product}: your {cadence} activity summary for {scope}",
        "welcome_subject": "{product}: welcome to {scope}",
        "security_subject": "{product}: account security activity in {scope}",
        "security_client_changed": "An OAuth application client configuration was changed.",
        "digest_description": (
            "The knowledge you created, updated and consulted, and the projects you worked in."
        ),
        "digest_action": "Manage my summaries",
        "digest_footer": (
            "This optional summary is enabled in your preferences. You can change its "
            "schedule or turn it off. "
        ),
        "preferences": "Preferences and subscription",
        "accept": "Accept",
        "decline": "Decline",
        "sign_in": "Sign in with SSO",
        "sign_out": "Switch account",
        "unavailable": "This invitation is unavailable for the signed-in account.",
        "invitation_closed": "This invitation is already closed.",
        "organization": "Organization",
        "workspace": "Workspace",
        "access_granted_title": "Access granted",
        "access_granted_body": "A role assignment was added to your account.",
        "role_changed_title": "Role assignment changed",
        "role_changed_body": "A role assignment on your account was changed.",
        "access_removed_title": "Role assignment removed",
        "access_removed_body": (
            "A role assignment was removed from your account. Other role assignments may still grant access."
        ),
        "security_title": "Account security activity",
        "security_token_created": "An API token was created for your account.",
        "security_token_revoked": "An API token for your account was revoked.",
        "security_application_granted": "An application connection was authorized for your account.",
        "security_application_revoked": "An application connection for your account was revoked.",
        "security_client_registered": "An OAuth application client was registered.",
        "security_client_revoked": "An OAuth application client was revoked.",
        "security_client_secret_rotated": "An OAuth application client's secret was rotated.",
        "security_footer": (
            "This required security notice describes a recorded account change. No credential is included."
        ),
        "mcp_summary_unavailable": "MCP activity is not included in this summary yet.",
        "requests": "Requests to {assistant}",
        "completed": "Completed",
        "failed": "Failed",
        "daily": "daily",
        "weekly": "weekly",
        "monthly": "monthly",
        "role_viewer": "viewer",
        "role_analyst": "analyst",
        "role_editor": "editor",
        "role_operator": "operator",
        "role_admin": "administrator",
        "welcome_heading": "Welcome to {product}",
        "welcome_pending_description": (
            "An initial organization administrator enrollment is reserved for your corporate identity. "
            "Sign in with SSO to verify your identity and activate access."
        ),
        "welcome_description": (
            "Your administrator access is ready. Sign in with your corporate account to "
            "configure your organization."
        ),
        "welcome_action": "Open the setup guide",
        "welcome_footer": "Use SSO to sign in. This message contains no password or access token.",
        "inbox": "Notifications",
        "welcome_title": "Welcome",
        "welcome_body": (
            "Your administrator access is ready. Sign in with your corporate account to get started."
        ),
        "invitation_title": "Invitation",
        "invitation_body": "You have an invitation to review.",
        "digest_title": "Activity summary",
        "digest_body": "A summary of currently accessible activity is available.",
        "save": "Save preferences",
    },
    "es": {
        "security_delivery_diagnostic_subject": "{product}: diagnóstico de entrega de correo para {scope}",
        "security_delivery_diagnostic": (
            "El operador de tu instalación ha solicitado este nuevo diagnóstico de entrega de correo "
            "para tu cuenta aprobada. No incluye credenciales ni contenido privado."
        ),
        "diagnostic_title": "Diagnóstico de entrega de correo",
        "diagnostic_footer": (
            "El operador de tu instalación ha solicitado este diagnóstico. "
            "Recibirlo no cambia tus permisos ni reintenta un mensaje anterior."
        ),
        "security_token_created_subject": "{product}: token de API creado en {scope}",
        "security_token_revoked_subject": "{product}: token de API revocado en {scope}",
        "security_application_granted_subject": "{product}: aplicación conectada en {scope}",
        "security_application_revoked_subject": "{product}: aplicación desconectada en {scope}",
        "security_client_registered_subject": "{product}: cliente OAuth registrado en {scope}",
        "security_client_revoked_subject": "{product}: cliente OAuth revocado en {scope}",
        "security_client_secret_rotated_subject": "{product}: secreto de cliente OAuth renovado en {scope}",
        "security_client_changed_subject": "{product}: configuración de cliente OAuth modificada en {scope}",
        "invite_subject": "{product}: invitación a {scope}",
        "invite_heading": "Te invitamos a colaborar",
        "invite_by": "{actor} te ha invitado a colaborar en {organization}.",
        "team_fallback": "El equipo de {organization}",
        "invite_action": "Revisar invitación",
        "invite_footer": (
            "Esta invitación está vinculada a tu cuenta corporativa. Reenviar el enlace no "
            "concede acceso a otra persona."
        ),
        "invite_sign_in": (
            "Inicia sesión con tu cuenta corporativa para revisar el acceso. Podrás aceptar "
            "o rechazar la invitación antes de que se conceda ningún permiso."
        ),
        "invite_scope": "Acceso propuesto: {scope}, rol de {role}.",
        "invite_expiry": "La invitación caduca el {expiry}.",
        "administrative_digest_heading": "Resumen de actividad de la organización",
        "administrative_digest_subject": (
            "{product}: resumen {cadence} de actividad de la organización {scope}"
        ),
        "administrative_digest_description": (
            "El conocimiento creado, actualizado y consultado en los proyectos "
            "de la organización a los que tienes acceso."
        ),
        "project_total": "{count} actividades",
        "project_created": "Creadas",
        "project_updated": "Actualizadas",
        "project_consulted": "Consultadas",
        "project_counts_description": (
            "La actividad registrada suma los recuentos de creaciones, actualizaciones y consultas. "
            "Una pieza puede aparecer en más de una categoría."
        ),
        "digest_heading": "Tu resumen de actividad",
        "digest_subject": "{product}: tu resumen {cadence} de actividad en {scope}",
        "welcome_subject": "{product}: bienvenido a {scope}",
        "security_subject": "{product}: actividad de seguridad en {scope}",
        "security_client_changed": "Se ha modificado la configuración de un cliente de aplicación OAuth.",
        "digest_description": (
            "El conocimiento que has creado, actualizado y consultado, y los proyectos en "
            "los que has trabajado."
        ),
        "digest_action": "Configurar mis resúmenes",
        "digest_footer": (
            "Recibes este resumen opcional porque lo has activado. Puedes cambiar su horario "
            "o desactivarlo. Los recuentos corresponden a solicitudes registradas del "
            "asistente."
        ),
        "preferences": "Preferencias y suscripción",
        "accept": "Aceptar",
        "decline": "Rechazar",
        "sign_in": "Iniciar sesión con SSO",
        "sign_out": "Cambiar de cuenta",
        "unavailable": "Esta invitación no está disponible para la cuenta que ha iniciado sesión.",
        "invitation_closed": "Esta invitación ya está cerrada.",
        "organization": "Organización",
        "workspace": "Espacio de trabajo",
        "access_granted_title": "Acceso concedido",
        "access_granted_body": "Se ha añadido una asignación de rol a tu cuenta.",
        "role_changed_title": "Asignación de rol modificada",
        "role_changed_body": "Se ha modificado una asignación de rol de tu cuenta.",
        "access_removed_title": "Asignación de rol retirada",
        "access_removed_body": (
            "Se ha retirado una asignación de rol de tu cuenta. Otras asignaciones pueden "
            "seguir dando acceso."
        ),
        "security_title": "Actividad de seguridad de tu cuenta",
        "security_token_created": "Se ha creado un token de API para tu cuenta.",
        "security_token_revoked": "Se ha revocado un token de API de tu cuenta.",
        "security_application_granted": "Se ha autorizado una conexión de aplicación para tu cuenta.",
        "security_application_revoked": "Se ha revocado una conexión de aplicación de tu cuenta.",
        "security_client_registered": "Se ha registrado un cliente de aplicación OAuth.",
        "security_client_revoked": "Se ha revocado un cliente de aplicación OAuth.",
        "security_client_secret_rotated": "Se ha renovado el secreto de un cliente de aplicación OAuth.",
        "security_footer": (
            "Este aviso de seguridad obligatorio describe un cambio registrado en tu cuenta. "
            "No incluye ninguna credencial."
        ),
        "mcp_summary_unavailable": "La actividad de MCP todavía no se incluye en este resumen.",
        "requests": "Solicitudes a {assistant}",
        "completed": "Completadas",
        "failed": "Fallidas",
        "daily": "diario",
        "weekly": "semanal",
        "monthly": "mensual",
        "role_viewer": "lector",
        "role_analyst": "analista",
        "role_editor": "editor",
        "role_operator": "operador",
        "role_admin": "administrador",
        "welcome_heading": "Bienvenido a {product}",
        "welcome_pending_description": (
            "Se ha reservado una incorporación como administrador de la organización para tu identidad "
            "corporativa. Inicia sesión con SSO para verificar tu identidad y activar el acceso."
        ),
        "welcome_description": (
            "Tu acceso de administrador está preparado. Inicia sesión con tu cuenta "
            "corporativa para configurar la organización."
        ),
        "welcome_action": "Abrir la guía de configuración",
        "welcome_footer": (
            "Utiliza SSO para iniciar sesión. Este mensaje no contiene contraseñas ni tokens de acceso."
        ),
        "inbox": "Notificaciones",
        "welcome_title": "Bienvenido",
        "welcome_body": (
            "Tu acceso de administrador está preparado. Inicia sesión con tu cuenta "
            "corporativa para comenzar."
        ),
        "invitation_title": "Invitación",
        "invitation_body": "Tienes una invitación para revisar.",
        "digest_title": "Resumen de actividad",
        "digest_body": "Hay un resumen de la actividad a la que tienes acceso.",
        "save": "Guardar preferencias",
    },
}


def translate(locale, key, **values):
    language = normalize_locale(locale).split("-", 1)[0]
    return _COPY[language][key].format(**values)


def subject_line(locale, *, product, kind, scope, cadence="weekly", subtype=None):
    if kind not in {
        "invitation",
        "welcome",
        "security",
        "digest",
        "administrative_digest",
    } or cadence not in {
        "daily",
        "weekly",
        "monthly",
    }:
        raise ValueError("Use a fixed communication purpose")
    for value in (product, scope):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 512
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise ValueError("Email subjects require bounded readable brand and scope labels")
    key = "invite_subject" if kind == "invitation" else kind + "_subject"
    if kind == "security" and subtype is not None:
        allowed = {
            "delivery_diagnostic",
            "token_created",
            "token_revoked",
            "application_granted",
            "application_revoked",
            "client_registered",
            "client_revoked",
            "client_secret_rotated",
            "client_changed",
        }
        if subtype not in allowed:
            raise ValueError("Use an allowlisted security subject purpose")
        key = "security_" + subtype + "_subject"
    values = dict(product=product.strip(), scope=scope.strip(), cadence=translate(locale, cadence))
    result = translate(locale, key, **values)
    if len(result) > 240:
        available = 240 - (len(result) - len(values["scope"]))
        if available < 1:
            raise ValueError("The product label exceeds the email subject boundary")
        values["scope"] = values["scope"][:available].rstrip()
        result = translate(locale, key, **values)
    return result
