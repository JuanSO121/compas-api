# ===== app/routes/auth.py =====
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timedelta

from app.models.auth import UserRegistration, UserLogin, PasswordReset, PasswordResetConfirm, TokenPair, TokenRefresh
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

@router.post("/register", response_model=dict)
async def register_user(user_data: UserRegistration, request: Request):
    """Registro de usuario accesible"""
    try:
        # Validaciones accesibles
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
                    suggestion="Use un email diferente o inicie sesión si ya tiene cuenta"
                )],
                accessibility_info={
                    "announcement": "Email ya registrado. ¿Desea iniciar sesión en su lugar?",
                    "focus_element": "email-field",
                    "haptic_pattern": "warning"
                }
            )

        # Crear usuario
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

        # ✅ CAMBIO: Enviar código de verificación
        verification_code = new_user["security"]["email_verification_code"]["code"]
        email_sent = await email_service.send_verification_code_email(
            email=new_user["email"],
            code=verification_code,
            user_name=new_user["profile"].get("first_name", ""),
            expires_minutes=15
        )

        success_message = "Cuenta creada exitosamente. Revise su email para el código de verificación de 6 dígitos."
        if not email_sent:
            success_message += " Nota: No pudimos enviar el email de verificación, pero puede solicitar uno nuevo más tarde."

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=success_message,
            data={
                "user_id": str(new_user["_id"]),
                "email": new_user["email"],
                "verification_required": True,
                "verification_method": "code",  # ✅ NUEVO
                "email_sent": email_sent
            },
            accessibility_info={
                "announcement": "Cuenta creada. Revise su email para el código de 6 dígitos.",
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
        
@router.post("/login", response_model=dict)
async def login_user(login_data: UserLogin, request: Request):
    """Login de usuario accesible"""
    try:
        # Validar email
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

        # Autenticar usuario
        user = await auth_service.authenticate_user(login_data.email, login_data.password)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email o contraseña incorrectos",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Credenciales inválidas",
                    field="password",
                    suggestion="Verifique su email y contraseña, o use 'Olvidé mi contraseña'"
                )],
                accessibility_info={
                    "announcement": "Email o contraseña incorrectos. Verifique sus datos.",
                    "focus_element": "password-field", 
                    "haptic_pattern": "error"
                }
            )

        # Verificar si la cuenta está verificada
        if not user.get("is_verified", False):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Debe verificar su email antes de iniciar sesión",
                data={"requires_verification": True, "email": user["email"]},
                accessibility_info={
                    "announcement": "Cuenta no verificada. Revise su email para verificar su cuenta.",
                    "focus_element": "verification-message",
                    "haptic_pattern": "warning"
                }
            )

        # Crear tokens
        token_pair = auth_service.create_token_pair(user)
        
        # Preparar datos del usuario (sin información sensible)
        user_data = {
            "id": str(user["_id"]),
            "email": user["email"],
            "profile": user.get("profile", {}),
            "accessibility": user.get("accessibility", {}),
            "last_login": user.get("security", {}).get("last_login")
        }

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=f"Bienvenido de vuelta{', ' + user.get('profile', {}).get('first_name', '') if user.get('profile', {}).get('first_name') else ''}",
            data={
                "tokens": token_pair.dict(),
                "user": user_data
            },
            accessibility_info={
                "announcement": f"Sesión iniciada exitosamente. Bienvenido{', ' + user.get('profile', {}).get('first_name', '') if user.get('profile', {}).get('first_name') else ''}.",
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
                "announcement": "Error del servidor. Intente nuevamente en unos momentos.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )

@router.post("/refresh", response_model=dict)
async def refresh_token(refresh_data: TokenRefresh):
    """Renovar token de acceso"""
    try:
        # Verificar refresh token
        payload = await auth_service.verify_token(refresh_data.refresh_token, "refresh")
        if not payload:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Token de renovación inválido o expirado",
                accessibility_info={
                    "announcement": "Sesión expirada. Inicie sesión nuevamente.",
                    "focus_element": "login-form",
                    "haptic_pattern": "warning"
                }
            )

        # Obtener usuario
        user_id = payload.get("sub")
        user = await users_collection.find_user_by_id(user_id)
        if not user or not user.get("is_active"):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Usuario no encontrado o inactivo",
                accessibility_info={
                    "announcement": "Usuario no válido. Inicie sesión nuevamente.",
                    "focus_element": "login-form",
                    "haptic_pattern": "error"
                }
            )

        # Crear nuevo par de tokens
        new_token_pair = auth_service.create_token_pair(user)

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Token renovado exitosamente",
            data={"tokens": new_token_pair.dict()},
            accessibility_info={
                "announcement": "Sesión renovada exitosamente",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error renovando token: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error renovando la sesión",
            accessibility_info={
                "announcement": "Error renovando sesión. Inicie sesión nuevamente.",
                "focus_element": "login-form",
                "haptic_pattern": "error"
            }
        )

@router.post("/logout", response_model=dict)
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout de usuario"""
    try:
        # En un sistema más complejo, aquí se invalidaría el token en una blacklist
        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Sesión cerrada exitosamente",
            accessibility_info={
                "announcement": "Sesión cerrada. Hasta pronto.",
                "focus_element": "login-form",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en logout: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error cerrando sesión",
            accessibility_info={
                "announcement": "Error cerrando sesión",
                "haptic_pattern": "error"
            }
        )

@router.post("/forgot-password", response_model=dict)
async def forgot_password(reset_data: PasswordReset):
    """Solicitar reseteo de contraseña"""
    try:
        # Validar email
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

        # Buscar usuario
        user = await users_collection.find_user_by_email(reset_data.email)
        
        # Por seguridad, siempre responder exitosamente (no revelar si el email existe)
        success_message = "Si el email existe en nuestro sistema, recibirá instrucciones para resetear su contraseña."
        
        if user and user.get("is_active", False):
            # Generar token de reseteo
            reset_token = auth_service.generate_verification_token()
            reset_data_dict = {
                "token": reset_token,
                "expires": datetime.utcnow() + timedelta(hours=1),
                "used": False
            }
            
            # Actualizar usuario con token de reseteo
            await users_collection.update_user(
                str(user["_id"]),
                {"security.password_reset_tokens": [reset_data_dict]}
            )
            
            # Enviar email
            await email_service.send_password_reset_email(
                email=user["email"],
                token=reset_token,
                user_name=user.get("profile", {}).get("first_name", "")
            )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message=success_message,
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
        # Validar nueva contraseña
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

        # Buscar usuario con token válido
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

        # Actualizar contraseña
        new_password_hash = auth_service.hash_password(reset_data.new_password)
        
        await users_collection.update_user(
            str(user["_id"]),
            {
                "password_hash": new_password_hash,
                "security.password_reset_tokens": [],  # Limpiar tokens
                "security.failed_login_attempts": 0,   # Resetear intentos fallidos
                "security.account_locked_until": None  # Desbloquear cuenta
            }
        )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Contraseña actualizada exitosamente. Ya puede iniciar sesión.",
            accessibility_info={
                "announcement": "Contraseña actualizada exitosamente. Redirigiendo al inicio de sesión.",
                "focus_element": "login-form",
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

@router.post("/verify-email", response_model=dict)
async def verify_email(token: str):
    """Verificar email de usuario"""
    try:
        # Buscar usuario con token de verificación
        user = await users_collection.find_user_by_email_verification_token(token)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Token de verificación inválido o expirado",
                accessibility_info={
                    "announcement": "Enlace de verificación inválido. Solicite uno nuevo.",
                    "focus_element": "error-message",
                    "haptic_pattern": "error"
                }
            )

        # Verificar cuenta
        await users_collection.update_user(
            str(user["_id"]),
            {
                "is_verified": True,
                "security.email_verification_token": None
            }
        )

        return AccessibleHelpers.create_accessible_response(
            success=True,
            message="Email verificado exitosamente. Su cuenta está ahora activa.",
            accessibility_info={
                "announcement": "Email verificado exitosamente. Cuenta activada. Redirigiendo al inicio de sesión.",
                "focus_element": "login-form",
                "haptic_pattern": "success"
            }
        )

    except Exception as e:
        logger.error(f"❌ Error en verificación de email: {e}")
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error verificando el email",
            accessibility_info={
                "announcement": "Error verificando email. Intente nuevamente.",
                "focus_element": "error-message",
                "haptic_pattern": "error"
            }
        )
        
@router.post("/send-verification-code", response_model=dict)
async def send_verification_code(email_data: dict, request: Request):
    """Enviar código de verificación por email"""
    try:
        from app.services.verification_service import verification_service
        from app.services.security_service import security_service
        
        email = email_data.get("email")
        if not email:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email requerido",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Debe proporcionar un email",
                    field="email"
                )],
                accessibility_info={
                    "announcement": "Error: Email requerido",
                    "focus_element": "email-field",
                    "haptic_pattern": "error"
                }
            )
        
        # Buscar usuario
        user = await users_collection.find_user_by_email(email)
        if not user:
            return AccessibleHelpers.create_accessible_response(
                success=True,
                message="Si el email existe, recibirá un código de verificación",
                accessibility_info={
                    "announcement": "Revise su email para el código de verificación",
                    "haptic_pattern": "info"
                }
            )
        
        # Si ya está verificado
        if user.get("is_verified", False):
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Esta cuenta ya está verificada",
                accessibility_info={
                    "announcement": "Cuenta ya verificada. Puede iniciar sesión.",
                    "haptic_pattern": "info"
                }
            )
        
        # Enviar código
        user_name = user.get("profile", {}).get("first_name", "")
        email_sent = await verification_service.send_verification_code(email, user_name)
        
        if email_sent:
            return AccessibleHelpers.create_accessible_response(
                success=True,
                message="Código de verificación enviado. Revise su email.",
                data={
                    "expires_in_minutes": verification_service.CODE_EXPIRATION_MINUTES,
                    "max_attempts": verification_service.MAX_ATTEMPTS
                },
                accessibility_info={
                    "announcement": f"Código enviado. Tiene {verification_service.CODE_EXPIRATION_MINUTES} minutos para ingresarlo.",
                    "haptic_pattern": "success"
                }
            )
        else:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Error enviando el código. Intente nuevamente.",
                accessibility_info={
                    "announcement": "Error enviando código. Intente nuevamente.",
                    "haptic_pattern": "error"
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Error enviando código: {e}")
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


@router.post("/verify-code", response_model=dict)
async def verify_code_endpoint(verification_data: dict):
    """Verificar código de verificación"""
    try:
        from app.services.verification_service import verification_service
        
        email = verification_data.get("email")
        code = verification_data.get("code")
        
        if not email or not code:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Email y código son requeridos",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Faltan datos requeridos",
                    field="email" if not email else "code"
                )],
                accessibility_info={
                    "announcement": "Error: Falta información requerida",
                    "focus_element": "email-field" if not email else "code-field",
                    "haptic_pattern": "error"
                }
            )
        
        # Limpiar y validar código
        code = code.strip().replace(" ", "")
        if not code.isdigit() or len(code) != 6:
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message="Código inválido. Debe ser de 6 dígitos.",
                errors=[AccessibleHelpers.create_accessible_error(
                    message="Formato de código inválido",
                    field="code",
                    suggestion="Ingrese los 6 dígitos del código"
                )],
                accessibility_info={
                    "announcement": "Código inválido. Ingrese 6 dígitos.",
                    "focus_element": "code-field",
                    "haptic_pattern": "error"
                }
            )
        
        # Verificar código
        result = await verification_service.verify_code(email, code)
        
        if result["success"]:
            return AccessibleHelpers.create_accessible_response(
                success=True,
                message="¡Email verificado exitosamente! Ya puede iniciar sesión.",
                data={"verified": True},
                accessibility_info={
                    "announcement": "Email verificado exitosamente. Redirigiendo al inicio de sesión.",
                    "haptic_pattern": "success"
                }
            )
        else:
            error_messages = {
                "user_not_found": "Usuario no encontrado",
                "no_code": "No hay código activo. Solicite uno nuevo.",
                "expired": "Código expirado. Solicite uno nuevo.",
                "max_attempts": "Demasiados intentos. Solicite un nuevo código.",
                "invalid_code": result.get("message", "Código incorrecto"),
                "server_error": "Error del servidor. Intente nuevamente."
            }
            
            error_type = result.get("error_type", "server_error")
            message = error_messages.get(error_type, result.get("message"))
            
            return AccessibleHelpers.create_accessible_response(
                success=False,
                message=message,
                data={
                    "error_type": error_type,
                    "remaining_attempts": result.get("remaining_attempts")
                },
                errors=[AccessibleHelpers.create_accessible_error(
                    message=message,
                    field="code",
                    suggestion="Verifique el código e intente nuevamente" if error_type == "invalid_code" else "Solicite un nuevo código"
                )],
                accessibility_info={
                    "announcement": message,
                    "focus_element": "code-field" if error_type == "invalid_code" else "resend-button",
                    "haptic_pattern": "error"
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Error verificando código: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return AccessibleHelpers.create_accessible_response(
            success=False,
            message="Error interno verificando el código",
            accessibility_info={
                "announcement": "Error del servidor. Intente nuevamente.",
                "haptic_pattern": "error"
            }
        )
        
@router.post("/debug-hash", response_model=dict)
async def debug_hash(data: dict):
    test_hash = "$2b$12$DSqcpKApwedQ85S6fYzOEe7Qkmkf4DbBETVRsYx0qAQggsYhoZSIa"
    password = data.get("password", "")
    result = auth_service.verify_password(password, test_hash)
    new_hash = auth_service.hash_password(password)
    return {"verified": result, "new_hash": new_hash}


