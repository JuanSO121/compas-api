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
# REGISTRO — sin contraseña
# ══════════════════════════════════════════════════════════════════

@router.post("/register", response_model=dict)
async def register_user(user_data: UserRegistration, request: Request):
    """
    Registro de usuario sin contraseña.
    Al completarse, se genera un código de acceso PERMANENTE y se envía al email.
    Ese código de 6 dígitos es la única credencial necesaria para iniciar sesión.
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

        # Verificar si el email ya existe
        existing_user = await users_collection.find_user_by_email(
            email_validation["normalized_email"]
        )
        if existing_user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Ya existe una cuenta con este email",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Email ya registrado",
                    field="email",
                    suggestion="Use un email diferente o ingrese con su código de acceso"
                )],
                accessibility_info={
                    "announcement": "Email ya registrado. ¿Desea iniciar sesión con su código?",
                    "focus_element": "email-field",
                    "haptic_pattern": "warning"
                }
            )

        # Construir el dict del usuario SIN contraseña
        # password_hash queda vacío — el acceso es exclusivamente por código permanente.
        user_dict = {
            "email": email_validation["normalized_email"],
            "password_hash": "",  # sin contraseña
            "profile": {
                "first_name": user_data.first_name,
                "last_name": user_data.last_name,
                "preferred_language": user_data.preferred_language,
                "timezone": "America/Bogota"
            },
            "accessibility": {
                # Campos que SÍ persisten en BD
                "visual_impairment_level": user_data.visual_impairment_level,
                "screen_reader_user": user_data.screen_reader_user,
                "preferred_tts_speed": 1.0,
                "high_contrast_mode": False,
                "dark_mode_enabled": False,
                "haptic_feedback_enabled": True,
                "audio_descriptions_enabled": (
                    user_data.visual_impairment_level in ["blind", "low_vision"]
                ),
                "voice_commands_enabled": False,
                "extended_timeout_needed": (
                    user_data.visual_impairment_level == "blind"
                ),
                "audio_confirmation_enabled": True,
                "skip_repetitive_content": True,
                "landmark_navigation_preferred": True,
                # Campos que NO persisten en BD (los maneja el dispositivo):
                # preferred_font_size, gesture_navigation_enabled,
                # slow_animations, custom_notification_sounds
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

        # Enviar email con el código permanente
        permanent_code = new_user["security"]["permanent_access_code"]
        user_name = new_user["profile"].get("first_name") or ""

        email_sent = await email_service.send_permanent_access_code_email(
            email=new_user["email"],
            code=permanent_code,
            user_name=user_name,
            is_regenerated=False
        )

        success_message = (
            "¡Cuenta creada! Revise su email para encontrar su código de acceso. "
            "Ese código de 6 dígitos es lo único que necesita para ingresar a la aplicación."
        )
        if not email_sent:
            success_message += (
                " Nota: no pudimos enviar el email. "
                "Solicite su código desde la pantalla de inicio de sesión."
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
# LOGIN CON CÓDIGO PERMANENTE (flujo principal)
# ══════════════════════════════════════════════════════════════════

@router.post("/login-with-code", response_model=dict)
async def login_with_code(login_data: CodeLogin, request: Request):
    """
    Login principal: solo con el código de acceso permanente.
    No se necesita email ni contraseña.
    Si es el primer login, verifica la cuenta automáticamente.
    """
    try:
        code = login_data.code.strip().replace(" ", "")

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

        user = await users_collection.find_user_by_access_code(code)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Código de acceso incorrecto. Verifique el código en su email.",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Código no válido",
                    field="code",
                    suggestion=(
                        "Revise el email que recibió al registrarse. "
                        "Si perdió su código, use la opción 'Solicitar nuevo código'."
                    )
                )],
                accessibility_info={
                    "announcement": (
                        "Código incorrecto. Revise el email que recibió al registrarse. "
                        "Si no tiene el código, puede solicitar uno nuevo con su email."
                    ),
                    "focus_element": "code-field",
                    "haptic_pattern": "error"
                }
            )

        if not user.get("is_active", True):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Esta cuenta está desactivada. Contacte al soporte.",
                accessibility_info={
                    "announcement": "Cuenta desactivada. Contacte al soporte.",
                    "focus_element": "error-message",
                    "haptic_pattern": "error"
                }
            )

        # Primer login = verificación automática
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

        await users_collection.update_login_attempts(user["email"], increment=False)

        token_pair = auth_service.create_token_pair(user)

        name = user.get("profile", {}).get("first_name") or ""
        user_data_response = {
            "id": str(user["_id"]),
            "email": user["email"],
            "profile": user.get("profile", {}),
            "accessibility": user.get("accessibility", {}),
            "first_login": first_login
        }

        if first_login:
            welcome = f"¡Bienvenido{f', {name}' if name else ''}! Tu cuenta ha sido verificada."
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
                "user": user_data_response
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
# SOLICITAR NUEVO CÓDIGO — solo email, sin contraseña
# ══════════════════════════════════════════════════════════════════

@router.post("/request-new-code", response_model=dict)
async def request_new_code(data: RequestNewCode, request: Request):
    """
    Solicitar un nuevo código de acceso permanente.
    Solo requiere el email — sin contraseña.
    La respuesta es siempre la misma para evitar enumeración de usuarios.
    El código anterior queda invalidado al generar uno nuevo.
    """
    try:
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

        from app.services.verification_service import verification_service
        user = await users_collection.find_user_by_email(
            email_validation["normalized_email"]
        )

        if user and user.get("is_active", True):
            user_name = user.get("profile", {}).get("first_name") or ""
            # El servicio genera un nuevo código y lo envía.
            # No verificamos el resultado — la respuesta al cliente es siempre la misma.
            await verification_service.send_new_code_by_email(
                email=user["email"],
                user_name=user_name
            )

        # Respuesta genérica siempre (evita enumeración de usuarios)
        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=(
                "Si el email está registrado, recibirá su código de acceso en unos momentos. "
                "Revise también la carpeta de spam."
            ),
            accessibility_info={
                "announcement": (
                    "Si el email está registrado, recibirá su código en unos momentos. "
                    "Revise su bandeja de entrada y la carpeta de spam."
                ),
                "focus_element": "success-message",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error solicitando nuevo código: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno del servidor",
            accessibility_info={
                "announcement": "Error del servidor. Intente más tarde.",
                "haptic_pattern": "error"
            }
        )


# ══════════════════════════════════════════════════════════════════
# LOGIN CON EMAIL + CONTRASEÑA (secundario — solo usuarios legacy)
# ══════════════════════════════════════════════════════════════════

@router.post("/login", response_model=dict)
async def login_user(login_data: UserLogin, request: Request):
    """
    Login secundario con email y contraseña.
    Solo funciona para usuarios que tenían contraseña antes del cambio de flujo.
    Los usuarios nuevos (sin password_hash) no pueden usar este endpoint.
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
                    "announcement": "Email inválido.",
                    "focus_element": "email-field",
                    "haptic_pattern": "error"
                }
            )

        # Buscar usuario
        user = await users_collection.find_user_by_email(
            email_validation["normalized_email"]
        )

        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email o contraseña incorrectos",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Credenciales inválidas",
                    field="password",
                    suggestion="Use su código de acceso para iniciar sesión"
                )],
                accessibility_info={
                    "announcement": "Credenciales incorrectas.",
                    "focus_element": "password-field",
                    "haptic_pattern": "error"
                }
            )

        # Verificar que este usuario tiene contraseña (no es usuario nuevo)
        password_hash = user.get("password_hash", "")
        if not password_hash:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Esta cuenta usa código de acceso. Ingrese con su código.",
                accessibility_info={
                    "announcement": (
                        "Esta cuenta no tiene contraseña. "
                        "Use su código de acceso para iniciar sesión."
                    ),
                    "focus_element": "code-field",
                    "haptic_pattern": "warning"
                }
            )

        user_authenticated = await auth_service.authenticate_user(
            login_data.email, login_data.password
        )
        if not user_authenticated:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email o contraseña incorrectos",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Credenciales inválidas",
                    field="password",
                    suggestion="Verifique sus datos o use su código de acceso"
                )],
                accessibility_info={
                    "announcement": "Email o contraseña incorrectos.",
                    "focus_element": "password-field",
                    "haptic_pattern": "error"
                }
            )

        if not user_authenticated.get("is_verified", False):
            await users_collection.update_user(
                str(user_authenticated["_id"]),
                {
                    "is_verified": True,
                    "security.email_verified_at": datetime.utcnow()
                }
            )
            user_authenticated["is_verified"] = True

        token_pair = auth_service.create_token_pair(user_authenticated)
        name = user_authenticated.get("profile", {}).get("first_name") or ""

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=f"Bienvenido{f', {name}' if name else ''}",
            data={
                "tokens": token_pair.dict(),
                "user": {
                    "id": str(user_authenticated["_id"]),
                    "email": user_authenticated["email"],
                    "profile": user_authenticated.get("profile", {}),
                    "accessibility": user_authenticated.get("accessibility", {}),
                }
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
# RESETEO DE CONTRASEÑA (legacy — para usuarios con password_hash)
# ══════════════════════════════════════════════════════════════════

@router.post("/forgot-password", response_model=dict)
async def forgot_password(reset_data: PasswordReset):
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

        if user and user.get("is_active", False) and user.get("password_hash", ""):
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
            message="Si el email existe, recibirá instrucciones para resetear su contraseña.",
            accessibility_info={
                "announcement": "Revise su email para las instrucciones de reseteo.",
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
    try:
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
            message="Contraseña actualizada. Use su código de acceso para iniciar sesión.",
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