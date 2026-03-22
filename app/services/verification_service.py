# ===== app/services/verification_service.py =====
import secrets
import string
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.database.collections import users_collection
from app.services.email_service import email_service
import logging

logger = logging.getLogger(__name__)


class VerificationService:
    """Servicio de verificación - códigos permanentes y temporales"""

    # ─────────────────────────────────────────────────────────────
    # CONFIGURACIÓN CÓDIGO PERMANENTE
    # ─────────────────────────────────────────────────────────────
    # El código permanente es la credencial principal de login.
    # Se genera una vez al registrarse y se envía al correo.
    # El usuario lo guarda y lo usa siempre para ingresar.
    PERMANENT_CODE_LENGTH = 6  # Puedes subir a 8 para mayor seguridad

    # ─────────────────────────────────────────────────────────────
    # CONFIGURACIÓN CÓDIGO TEMPORAL (legacy / verificación manual)
    # ─────────────────────────────────────────────────────────────
    CODE_LENGTH = 6
    CODE_EXPIRATION_MINUTES = 15
    MAX_ATTEMPTS = 5

    # ─────────────────────────────────────────────────────────────
    # MÉTODOS CÓDIGO PERMANENTE
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_permanent_access_code() -> str:
        """Generar código numérico permanente"""
        return ''.join(
            secrets.choice(string.digits)
            for _ in range(VerificationService.PERMANENT_CODE_LENGTH)
        )

    @staticmethod
    async def generate_unique_access_code() -> str:
        """
        Generar un código permanente garantizando que sea único en la BD.
        Con 6 dígitos hay 1.000.000 de combinaciones posibles.
        El bucle se repite en el improbable caso de colisión.
        """
        max_attempts = 20
        for attempt in range(max_attempts):
            code = VerificationService.generate_permanent_access_code()
            existing = await users_collection.find_user_by_access_code(code)
            if not existing:
                return code
            logger.warning(f"⚠️ Código {code} ya existe, generando otro (intento {attempt + 1})")

        # Si después de 20 intentos sigue colisionando, algo está muy mal
        raise RuntimeError(
            "No se pudo generar un código de acceso único. "
            "Considere aumentar PERMANENT_CODE_LENGTH."
        )

    @staticmethod
    async def assign_permanent_code_to_user(user_id: str) -> Optional[str]:
        """
        Generar y guardar un nuevo código permanente para un usuario.
        Retorna el código generado, o None si hubo error.
        Úsalo también cuando el usuario pide regenerar su código (recuperación).
        """
        try:
            code = await VerificationService.generate_unique_access_code()

            success = await users_collection.update_user(
                user_id,
                {
                    "security.permanent_access_code": code,
                    "security.code_regenerated_at": datetime.utcnow()
                }
            )

            if success:
                logger.info(f"✅ Código permanente asignado al usuario {user_id}")
                return code

            logger.error(f"❌ No se pudo guardar el código para el usuario {user_id}")
            return None

        except Exception as e:
            logger.error(f"❌ Error asignando código permanente: {e}")
            return None

    @staticmethod
    async def send_new_code_by_email(email: str, user_name: str = "") -> bool:
        """
        Generar nuevo código permanente para un usuario y enviarlo por email.
        Se usa en el endpoint de recuperación /request-new-code.
        """
        try:
            user = await users_collection.find_user_by_email(email)
            if not user:
                return False

            # Generar y guardar nuevo código
            new_code = await VerificationService.assign_permanent_code_to_user(str(user["_id"]))
            if not new_code:
                return False

            # Enviar email con el nuevo código permanente
            return await email_service.send_permanent_access_code_email(
                email=email,
                code=new_code,
                user_name=user_name,
                is_regenerated=True  # indica que es un código nuevo (no el primero)
            )

        except Exception as e:
            logger.error(f"❌ Error enviando nuevo código: {e}")
            return False

    # ─────────────────────────────────────────────────────────────
    # MÉTODOS CÓDIGO TEMPORAL (se mantienen por compatibilidad)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_verification_code() -> str:
        """Generar código numérico temporal de 6 dígitos (legacy)"""
        return ''.join(secrets.choice(string.digits) for _ in range(VerificationService.CODE_LENGTH))

    @staticmethod
    async def create_verification_code(user_id: str) -> Optional[Dict[str, Any]]:
        """Crear y guardar código de verificación temporal (legacy)"""
        try:
            code = VerificationService.generate_verification_code()
            expires_at = datetime.utcnow() + timedelta(minutes=VerificationService.CODE_EXPIRATION_MINUTES)

            verification_data = {
                "code": code,
                "expires_at": expires_at,
                "attempts": 0,
                "created_at": datetime.utcnow()
            }

            success = await users_collection.update_user(
                user_id,
                {"security.email_verification_code": verification_data}
            )

            if success:
                return verification_data
            return None

        except Exception as e:
            logger.error(f"❌ Error creando código de verificación temporal: {e}")
            return None

    @staticmethod
    async def send_verification_code(email: str, user_name: str = "") -> bool:
        """Enviar código de verificación temporal por email (legacy)"""
        try:
            user = await users_collection.find_user_by_email(email)
            if not user:
                return False

            verification_data = await VerificationService.create_verification_code(str(user["_id"]))
            if not verification_data:
                return False

            return await email_service.send_verification_code_email(
                email=email,
                code=verification_data["code"],
                user_name=user_name,
                expires_minutes=VerificationService.CODE_EXPIRATION_MINUTES
            )

        except Exception as e:
            logger.error(f"❌ Error enviando código temporal: {e}")
            return False

    @staticmethod
    async def verify_code(email: str, code: str) -> Dict[str, Any]:
        """Verificar código temporal (legacy)"""
        try:
            user = await users_collection.find_user_by_email(email)
            if not user:
                return {"success": False, "message": "Usuario no encontrado", "error_type": "user_not_found"}

            verification_data = user.get("security", {}).get("email_verification_code")
            if not verification_data:
                return {"success": False, "message": "No hay código activo. Solicite uno nuevo.", "error_type": "no_code"}

            expires_at = verification_data.get("expires_at")
            if datetime.utcnow() > expires_at:
                return {"success": False, "message": "El código ha expirado. Solicite uno nuevo.", "error_type": "expired"}

            attempts = verification_data.get("attempts", 0)
            if attempts >= VerificationService.MAX_ATTEMPTS:
                return {"success": False, "message": "Demasiados intentos. Solicite un nuevo código.", "error_type": "max_attempts"}

            stored_code = verification_data.get("code")
            if code != stored_code:
                await users_collection.update_user(
                    str(user["_id"]),
                    {"security.email_verification_code.attempts": attempts + 1}
                )
                remaining = VerificationService.MAX_ATTEMPTS - (attempts + 1)
                return {
                    "success": False,
                    "message": f"Código incorrecto. {remaining} intentos restantes.",
                    "error_type": "invalid_code",
                    "remaining_attempts": remaining
                }

            await users_collection.update_user(
                str(user["_id"]),
                {
                    "is_verified": True,
                    "security.email_verification_code": None,
                    "security.email_verified_at": datetime.utcnow()
                }
            )

            return {"success": True, "message": "Email verificado exitosamente", "user_id": str(user["_id"])}

        except Exception as e:
            logger.error(f"❌ Error verificando código temporal: {e}")
            return {"success": False, "message": "Error interno verificando el código", "error_type": "server_error"}


verification_service = VerificationService()