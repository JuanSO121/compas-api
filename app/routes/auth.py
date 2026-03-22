# ===== app/routes/auth.py =====
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timedelta

from app.models.auth import (
    UserRegistration, UserLogin, CodeLogin, RequestNewCode,
    PasswordReset, PasswordResetConfirm, TokenPair, TokenRefresh
)
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.user_service import user_service
from app.services.email_service import email_service
from app.database.collections import users_collection
from app.utils.helpers import AccessibleHelpers
from app.utils.validators import AccessibleValidators
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


# ══════════════════════════════════════════════════════════════════
# REGISTRO
# ══════════════════════════════════════════════════════════════════

@router.post("/register", response_model=dict)
async def register_user(user_data: UserRegistration, request: Request):
    """
    Registro de usuario.
    Al completarse, se envía un código de acceso PERMANENTE al email.
    Ese código es la única credencial necesaria para iniciar sesión.
    """
    try:
        # Validar email
        email_validation = AccessibleValidators.validate_email_accessible(user_data.email)
        if not email_validation["valid"]:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=email_validation["message"],
                errors=[AccessibleHelpers.create_accessible_error(
                    message=email_validation["message"],
                    field="email",
                    suggestion=email_validation.get("suggestions", ["Verifique el formato del email"])[0]
                )],
                accessibility_info={
                    "announcement": f"Error en email: {email_validation['message']}",
                    "focus_element": "email-field",
                    "haptic_pattern": "error"
                }
            )

        # Validar contraseña
        password_validation = AccessibleValidators.validate_password_accessible(user_data.password)
        if not password_validation["valid"]:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=password_validation["message"],
                errors=[AccessibleHelpers.create_accessible_error(
                    message=password_validation["message"],
                    field="password",
                    suggestion=password_validation.get("suggestions", ["Mejore la contraseña"])[0]
                )],
                accessibility_info={
                    "announcement": f"Error en contraseña: {password_validation['message']}",
                    "focus_element": "password-field",
                    "haptic_pattern": "error"
                }
            )

        # Verificar si el email ya existe
        existing_user = await users_collection.find_user_by_email(user_data.email)
        if existing_user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Ya existe una cuenta con este email",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Email ya registrado",
                    field="email",
                    suggestion="Use un email diferente o inicie sesión con su código de acceso"
                )],
                accessibility_info={
                    "announcement": "Email ya registrado. ¿Desea iniciar sesión con su código?",
                    "focus_element": "email-field",
                    "haptic_pattern": "warning"
                }
            )

        # Crear usuario (genera permanent_access_code internamente)
        user_dict = {
            "email": email_validation["normalized_email"],
            "password": user_data.password,
            "profile": {
                "first_name": user_data.first_name,
                "last_name": user_data.last_name,
                "preferred_language": user_data.preferred_language,
                "timezone": "America/Bogota"
            },
            "accessibility": {
                "visual_impairment_level": user_data.visual_impairment_level,
                "screen_reader_user": user_data.screen_reader_user,
                "preferred_tts_speed": 1.0,
                "preferred_font_size": "medium",
                "high_contrast_mode": False,
                "dark_mode_enabled": False,
                "haptic_feedback_enabled": True,
                "audio_descriptions_enabled": user_data.visual_impairment_level in ["blind", "low_vision"],
                "voice_commands_enabled": False,
                "gesture_navigation_enabled": True,
                "extended_timeout_needed": user_data.visual_impairment_level == "blind",
                "slow_animations": False,
                "custom_notification_sounds": False,
                "audio_confirmation_enabled": True,
                "skip_repetitive_content": True,
                "landmark_navigation_preferred": True
            }
        }

        new_user = await user_service.create_user(user_dict)
        if not new_user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Error creando la cuenta. Intente nuevamente.",
                accessibility_info={
                    "announcement": "Error creando cuenta. Intente nuevamente en unos momentos.",
                    "focus_element": "register-form",
                    "haptic_pattern": "error"
                }
            )

        # ── Enviar email con el código de acceso PERMANENTE ──
        permanent_code = new_user["security"]["permanent_access_code"]
        user_name = new_user["profile"].get("first_name", "")

        email_sent = await email_service.send_permanent_access_code_email(
            email=new_user["email"],
            code=permanent_code,
            user_name=user_name,
            is_regenerated=False
        )

        success_message = (
            "¡Cuenta creada! Revise su email para encontrar su código de acceso permanente. "
            "Ese código de 6 dígitos es lo único que necesita para ingresar a la aplicación."
        )
        if not email_sent:
            success_message += (
                " Nota: No pudimos enviar el email. "
                "Puede solicitar su código desde la pantalla de inicio de sesión."
            )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=success_message,
            data={
                "user_id": str(new_user["_id"]),
                "email": new_user["email"],
                "next_step": "login_with_code",
                "email_sent": email_sent
            },
            accessibility_info={
                "announcement": (
                    "Cuenta creada. Revise su correo electrónico para obtener su código de acceso. "
                    "Ese código de 6 dígitos es su llave para ingresar a la aplicación."
                ),
                "focus_element": "success-message",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en registro: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno del servidor durante el registro",
            accessibility_info={
                "announcement": "Error del servidor. Intente nuevamente en unos momentos.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# LOGIN CON CÓDIGO PERMANENTE (FLUJO PRINCIPAL)
# ══════════════════════════════════════════════════════════════════

@router.post("/login-with-code", response_model=dict)
async def login_with_code(login_data: CodeLogin, request: Request):
    """
    Login principal: solo con el código de acceso permanente.
    No se necesita email ni contraseña.

    - Si es el primer login: verifica la cuenta automáticamente.
    - Retorna tokens JWT para acceder a la aplicación.
    """
    try:
        # Limpiar código (espacios accidentales)
        code = login_data.code.strip().replace(" ", "")

        # Validar formato básico
        if not code.isdigit():
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="El código solo debe contener números.",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Formato de código incorrecto",
                    field="code",
                    suggestion="Ingrese solo los dígitos del código, sin espacios ni letras"
                )],
                accessibility_info={
                    "announcement": "Código incorrecto. Ingrese solo los números del código.",
                    "focus_element": "code-field",
                    "haptic_pattern": "error"
                }
            )

        # Buscar usuario por código
        user = await users_collection.find_user_by_access_code(code)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Código de acceso incorrecto. Verifique el código en su email.",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Código no válido",
                    field="code",
                    suggestion="Revise el email que recibió al registrarse. Si perdió su código, use la opción 'Solicitar nuevo código'."
                )],
                accessibility_info={
                    "announcement": (
                        "Código incorrecto. Revise el email que recibió al registrarse. "
                        "Si no tiene el código, puede solicitar uno nuevo con su email y contraseña."
                    ),
                    "focus_element": "code-field",
                    "haptic_pattern": "error"
                }
            )

        # Verificar cuenta activa
        if not user.get("is_active", True):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Esta cuenta está desactivada. Contacte al soporte.",
                accessibility_info={
                    "announcement": "Cuenta desactivada. Contacte al soporte para más información.",
                    "focus_element": "error-message",
                    "haptic_pattern": "error"
                }
            )

        # ── Primer login = verificación automática de la cuenta ──
        first_login = not user.get("is_verified", False)
        if first_login:
            await users_collection.update_user(
                str(user["_id"]),
                {
                    "is_verified": True,
                    "security.email_verified_at": datetime.utcnow(),
                    "security.permanent_code_first_used_at": datetime.utcnow()
                }
            )
            user["is_verified"] = True
            logger.info(f"✅ Cuenta verificada en primer login: {user['email']}")

        # Registrar login exitoso (resetear intentos fallidos y guardar fecha)
        await users_collection.update_login_attempts(user["email"], increment=False)

        # Crear tokens JWT
        token_pair = auth_service.create_token_pair(user)

        # Datos del usuario a retornar (sin info sensible)
        name = user.get("profile", {}).get("first_name", "")
        user_data = {
            "id": str(user["_id"]),
            "email": user["email"],
            "profile": user.get("profile", {}),
            "accessibility": user.get("accessibility", {}),
            "first_login": first_login
        }

        if first_login:
            welcome = f"¡Bienvenido{f', {name}' if name else ''}! Tu cuenta ha sido verificada exitosamente."
            announcement = (
                f"Bienvenido{f' {name}' if name else ''}. "
                "Tu cuenta ha sido verificada. Ahora puedes usar la aplicación."
            )
        else:
            welcome = f"Bienvenido de vuelta{f', {name}' if name else ''}."
            announcement = f"Sesión iniciada. Bienvenido de vuelta{f' {name}' if name else ''}."

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=welcome,
            data={
                "tokens": token_pair.dict(),
                "user": user_data
            },
            accessibility_info={
                "announcement": announcement,
                "focus_element": "main-content",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en login con código: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno durante el inicio de sesión",
            accessibility_info={
                "announcement": "Error del servidor. Intente nuevamente en unos momentos.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# RECUPERACIÓN: SOLICITAR NUEVO CÓDIGO
# ══════════════════════════════════════════════════════════════════

@router.post("/request-new-code", response_model=dict)
async def request_new_code(data: RequestNewCode, request: Request):
    """
    Solicitar un nuevo código de acceso permanente.
    Se usa cuando el usuario perdió u olvidó su código.
    Requiere email + contraseña para verificar la identidad.
    El nuevo código se envía al email y el anterior deja de funcionar.
    """
    try:
        # Validar email
        email_validation = AccessibleValidators.validate_email_accessible(data.email)
        if not email_validation["valid"]:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=email_validation["message"],
                errors=[AccessibleHelpers.create_accessible_error(
                    message=email_validation["message"],
                    field="email",
                    suggestion="Verifique el formato del email"
                )],
                accessibility_info={
                    "announcement": f"Email inválido: {email_validation['message']}",
                    "focus_element": "email-field",
                    "haptic_pattern": "error"
                }
            )

        # Autenticar con email + contraseña
        user = await auth_service.authenticate_user(data.email, data.password)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email o contraseña incorrectos.",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Credenciales inválidas",
                    field="password",
                    suggestion="Verifique su email y contraseña"
                )],
                accessibility_info={
                    "announcement": "Email o contraseña incorrectos. Verifique sus datos.",
                    "focus_element": "password-field",
                    "haptic_pattern": "error"
                }
            )

        # Generar y enviar nuevo código permanente
        from app.services.verification_service import verification_service
        user_name = user.get("profile", {}).get("first_name", "")

        email_sent = await verification_service.send_new_code_by_email(
            email=user["email"],
            user_name=user_name
        )

        if not email_sent:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Error enviando el nuevo código. Intente nuevamente.",
                accessibility_info={
                    "announcement": "Error enviando código. Intente nuevamente en unos momentos.",
                    "haptic_pattern": "error"
                }
            )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=(
                "Nuevo código enviado a su email. "
                "Revise su bandeja de entrada. "
                "El código anterior ya no funciona."
            ),
            accessibility_info={
                "announcement": (
                    "Nuevo código de acceso enviado a su correo electrónico. "
                    "Revise su bandeja de entrada. Recuerde que el código anterior ya no sirve."
                ),
                "focus_element": "success-message",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error solicitando nuevo código: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno del servidor",
            accessibility_info={
                "announcement": "Error del servidor. Intente más tarde.",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# LOGIN CON EMAIL + CONTRASEÑA (SECUNDARIO / ADMIN)
# ══════════════════════════════════════════════════════════════════

@router.post("/login", response_model=dict)
async def login_user(login_data: UserLogin, request: Request):
    """
    Login secundario con email y contraseña.
    Útil para administradores o cuando el usuario no tiene su código.
    También verifica la cuenta si aún no estaba verificada.
    """
    try:
        email_validation = AccessibleValidators.validate_email_accessible(login_data.email)
        if not email_validation["valid"]:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email inválido",
                errors=[AccessibleHelpers.create_accessible_error(
                    message=email_validation["message"],
                    field="email",
                    suggestion="Verifique el formato del email"
                )],
                accessibility_info={
                    "announcement": "Email inválido. Verifique el formato.",
                    "focus_element": "email-field",
                    "haptic_pattern": "error"
                }
            )

        user = await auth_service.authenticate_user(login_data.email, login_data.password)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email o contraseña incorrectos",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Credenciales inválidas",
                    field="password",
                    suggestion="Verifique sus datos o use su código de acceso para iniciar sesión"
                )],
                accessibility_info={
                    "announcement": "Email o contraseña incorrectos.",
                    "focus_element": "password-field",
                    "haptic_pattern": "error"
                }
            )

        # Si la cuenta no está verificada, la verificamos al entrar con contraseña
        if not user.get("is_verified", False):
            await users_collection.update_user(
                str(user["_id"]),
                {
                    "is_verified": True,
                    "security.email_verified_at": datetime.utcnow()
                }
            )
            user["is_verified"] = True

        token_pair = auth_service.create_token_pair(user)
        name = user.get("profile", {}).get("first_name", "")

        user_data = {
            "id": str(user["_id"]),
            "email": user["email"],
            "profile": user.get("profile", {}),
            "accessibility": user.get("accessibility", {}),
        }

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=f"Bienvenido{f', {name}' if name else ''}",
            data={
                "tokens": token_pair.dict(),
                "user": user_data
            },
            accessibility_info={
                "announcement": f"Sesión iniciada. Bienvenido{f' {name}' if name else ''}.",
                "focus_element": "main-content",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en login: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno durante el inicio de sesión",
            accessibility_info={
                "announcement": "Error del servidor. Intente nuevamente.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# RENOVAR TOKEN
# ══════════════════════════════════════════════════════════════════

@router.post("/refresh", response_model=dict)
async def refresh_token(refresh_data: TokenRefresh):
    """Renovar token de acceso"""
    try:
        payload = await auth_service.verify_token(refresh_data.refresh_token, "refresh")
        if not payload:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Token de renovación inválido o expirado",
                accessibility_info={
                    "announcement": "Sesión expirada. Ingrese su código de acceso nuevamente.",
                    "focus_element": "code-field",
                    "haptic_pattern": "warning"
                }
            )

        user_id = payload.get("sub")
        user = await users_collection.find_user_by_id(user_id)
        if not user or not user.get("is_active"):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Usuario no encontrado o inactivo",
                accessibility_info={
                    "announcement": "Usuario no válido. Ingrese su código nuevamente.",
                    "focus_element": "code-field",
                    "haptic_pattern": "error"
                }
            )

        new_token_pair = auth_service.create_token_pair(user)

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Sesión renovada exitosamente",
            data={"tokens": new_token_pair.dict()},
            accessibility_info={
                "announcement": "Sesión renovada",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error renovando token: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error renovando la sesión",
            accessibility_info={
                "announcement": "Error renovando sesión. Ingrese su código nuevamente.",
                "focus_element": "code-field",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════════

@router.post("/logout", response_model=dict)
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Cerrar sesión"""
    try:
        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Sesión cerrada exitosamente",
            accessibility_info={
                "announcement": "Sesión cerrada. Hasta pronto.",
                "focus_element": "code-field",
                "haptic_pattern": "success"
            }
        )
    except Exception as e:
        logger.error(f"❌ Error en logout: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error cerrando sesión",
            accessibility_info={"announcement": "Error cerrando sesión", "haptic_pattern": "error"}
        )


# ══════════════════════════════════════════════════════════════════
# RESETEO DE CONTRASEÑA (sin cambios)
# ══════════════════════════════════════════════════════════════════

@router.post("/forgot-password", response_model=dict)
async def forgot_password(reset_data: PasswordReset):
    """Solicitar reseteo de contraseña"""
    try:
        email_validation = AccessibleValidators.validate_email_accessible(reset_data.email)
        if not email_validation["valid"]:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=email_validation["message"],
                errors=[AccessibleHelpers.create_accessible_error(
                    message=email_validation["message"],
                    field="email",
                    suggestion="Verifique el formato del email"
                )],
                accessibility_info={
                    "announcement": f"Error en email: {email_validation['message']}",
                    "focus_element": "email-field",
                    "haptic_pattern": "error"
                }
            )

        user = await users_collection.find_user_by_email(reset_data.email)

        if user and user.get("is_active", False):
            reset_token = auth_service.generate_verification_token()
            reset_data_dict = {
                "token": reset_token,
                "expires": datetime.utcnow() + timedelta(hours=1),
                "used": False
            }
            await users_collection.update_user(
                str(user["_id"]),
                {"security.password_reset_tokens": [reset_data_dict]}
            )
            await email_service.send_password_reset_email(
                email=user["email"],
                token=reset_token,
                user_name=user.get("profile", {}).get("first_name", "")
            )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Si el email existe en nuestro sistema, recibirá instrucciones para resetear su contraseña.",
            accessibility_info={
                "announcement": "Revise su email para las instrucciones de reseteo de contraseña.",
                "focus_element": "success-message",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en forgot password: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error procesando solicitud de reseteo",
            accessibility_info={
                "announcement": "Error procesando solicitud. Intente nuevamente.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )


@router.post("/reset-password", response_model=dict)
async def reset_password(reset_data: PasswordResetConfirm):
    """Confirmar reseteo de contraseña"""
    try:
        password_validation = AccessibleValidators.validate_password_accessible(reset_data.new_password)
        if not password_validation["valid"]:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=password_validation["message"],
                errors=[AccessibleHelpers.create_accessible_error(
                    message=password_validation["message"],
                    field="new_password",
                    suggestion=password_validation.get("suggestions", ["Mejore la contraseña"])[0]
                )],
                accessibility_info={
                    "announcement": f"Error en contraseña: {password_validation['message']}",
                    "focus_element": "new-password-field",
                    "haptic_pattern": "error"
                }
            )

        from app.database.connection import get_database
        db = get_database()
        user = await db.users.find_one({
            "security.password_reset_tokens": {
                "$elemMatch": {
                    "token": reset_data.token,
                    "expires": {"$gt": datetime.utcnow()},
                    "used": False
                }
            }
        })

        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Token de reseteo inválido o expirado",
                accessibility_info={
                    "announcement": "Enlace de reseteo inválido. Solicite uno nuevo.",
                    "focus_element": "error-message",
                    "haptic_pattern": "error"
                }
            )

        new_password_hash = auth_service.hash_password(reset_data.new_password)
        await users_collection.update_user(
            str(user["_id"]),
            {
                "password_hash": new_password_hash,
                "security.password_reset_tokens": [],
                "security.failed_login_attempts": 0,
                "security.account_locked_until": None
            }
        )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Contraseña actualizada. Ya puede usar su código de acceso para iniciar sesión.",
            accessibility_info={
                "announcement": "Contraseña actualizada exitosamente.",
                "focus_element": "code-field",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en reset password: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error actualizando la contraseña",
            accessibility_info={
                "announcement": "Error actualizando contraseña. Intente nuevamente.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# ENDPOINTS LEGACY (mantenidos por compatibilidad)
# ══════════════════════════════════════════════════════════════════

@router.post("/send-verification-code", response_model=dict)
async def send_verification_code(email_data: dict, request: Request):
    """Enviar código temporal de verificación (legacy)"""
    try:
        from app.services.verification_service import verification_service

        email = email_data.get("email")
        if not email:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email requerido",
                accessibility_info={"announcement": "Error: Email requerido", "haptic_pattern": "error"}
            )

        user = await users_collection.find_user_by_email(email)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=True,
                message="Si el email existe, recibirá un código",
                accessibility_info={"announcement": "Revise su email", "haptic_pattern": "info"}
            )

        if user.get("is_verified", False):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Esta cuenta ya está verificada",
                accessibility_info={"announcement": "Cuenta ya verificada.", "haptic_pattern": "info"}
            )

        user_name = user.get("profile", {}).get("first_name", "")
        email_sent = await verification_service.send_verification_code(email, user_name)

        if email_sent:
            return AccessibleHelpers.create_accessible_response(
                success=True,
                message="Código temporal enviado.",
                accessibility_info={"announcement": "Código enviado.", "haptic_pattern": "success"}
            )
        else:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Error enviando el código.",
                accessibility_info={"announcement": "Error enviando código.", "haptic_pattern": "error"}
            )

    except Exception as e:
        logger.error(f"❌ Error enviando código legacy: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno del servidor",
            accessibility_info={"announcement": "Error del servidor.", "haptic_pattern": "error"}
        )


@router.post("/verify-code", response_model=dict)
async def verify_code_endpoint(verification_data: dict):
    """Verificar código temporal (legacy)"""
    try:
        from app.services.verification_service import verification_service

        email = verification_data.get("email")
        code = verification_data.get("code")

        if not email or not code:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email y código son requeridos",
                accessibility_info={"announcement": "Faltan datos requeridos", "haptic_pattern": "error"}
            )

        code = code.strip().replace(" ", "")
        if not code.isdigit() or len(code) != 6:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Código inválido. Debe ser de 6 dígitos.",
                accessibility_info={"announcement": "Código inválido.", "haptic_pattern": "error"}
            )

        result = await verification_service.verify_code(email, code)

        if result["success"]:
            return AccessibleHelpers.create_accessible_response(
                success=True,
                message="Email verificado exitosamente.",
                data={"verified": True},
                accessibility_info={"announcement": "Email verificado.", "haptic_pattern": "success"}
            )
        else:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=result.get("message", "Código incorrecto"),
                accessibility_info={"announcement": result.get("message", "Código incorrecto"), "haptic_pattern": "error"}
            )

    except Exception as e:
        logger.error(f"❌ Error verificando código legacy: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno verificando el código",
            accessibility_info={"announcement": "Error del servidor.", "haptic_pattern": "error"}
        )


@router.post("/debug-hash", response_model=dict)
async def debug_hash(data: dict):
    """Debug de hash (solo desarrollo)"""
    test_hash = "$2b$12$DSqcpKApwedQ85S6fYzOEe7Qkmkf4DbBETVRsYx0qAQggsYhoZSIa"
    password = data.get("password", "")
    result = auth_service.verify_password(password, test_hash)
    new_hash = auth_service.hash_password(password)
    return {"verified": result, "new_hash": new_hash}