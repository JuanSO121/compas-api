# ===== app/services/user_service.py =====
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app.database.collections import users_collection, accessibility_logs_collection
from app.models.user import User, AccessibilityPreferences
from app.models.accessibility import AccessibilityLog, AccessibilityEventType
from app.services.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Servicio de gestión de usuarios"""

    @staticmethod
    async def create_user(user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crear nuevo usuario.
        Genera un código de acceso permanente y lo guarda en el documento.
        El código se enviará al correo desde el endpoint de registro.
        """
        try:
            # Verificar si el email ya existe
            existing_user = await users_collection.find_user_by_email(user_data["email"])
            if existing_user:
                logger.warning(f"⚠️ Email ya existe: {user_data['email']}")
                return None

            # Hashear contraseña
            user_data["password_hash"] = AuthService.hash_password(user_data.pop("password"))

            # ─────────────────────────────────────────────────────────────
            # NUEVO: Generar código de acceso PERMANENTE (no temporal)
            # Este código es la credencial principal de login del usuario.
            # ─────────────────────────────────────────────────────────────
            from app.services.verification_service import verification_service

            permanent_code = await verification_service.generate_unique_access_code()

            if "security" not in user_data:
                user_data["security"] = {}

            user_data["security"]["permanent_access_code"] = permanent_code
            user_data["security"]["code_regenerated_at"] = datetime.utcnow()

            # La cuenta queda sin verificar hasta el primer login con código
            user_data["is_active"] = True
            user_data["is_verified"] = False

            # Crear usuario en la BD
            user = await users_collection.create_user(user_data)

            # Log de evento de accesibilidad
            await UserService.log_accessibility_event(
                str(user["_id"]),
                AccessibilityEventType.PREFERENCE_CHANGED,
                {
                    "event": "user_registered",
                    "accessibility_level": user_data.get("accessibility", {}).get("visual_impairment_level", "none")
                }
            )

            logger.info(f"✅ Usuario creado exitosamente: {user['email']}")
            return user

        except Exception as e:
            logger.error(f"❌ Error creando usuario: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Obtener perfil de usuario (sin datos sensibles)"""
        try:
            user = await users_collection.find_user_by_id(user_id)
            if user:
                user.pop("password_hash", None)
                user.pop("security", None)
            return user
        except Exception as e:
            logger.error(f"❌ Error obteniendo perfil: {e}")
            return None

    @staticmethod
    async def update_user_profile(user_id: str, update_data: Dict[str, Any]) -> bool:
        """Actualizar perfil de usuario"""
        try:
            # Remover campos que no se deben actualizar directamente
            forbidden_fields = ["password_hash", "_id", "created_at", "email"]
            for field in forbidden_fields:
                update_data.pop(field, None)

            success = await users_collection.update_user(user_id, update_data)

            if success:
                await UserService.log_accessibility_event(
                    user_id,
                    AccessibilityEventType.PREFERENCE_CHANGED,
                    {"event": "profile_updated", "fields_updated": list(update_data.keys())}
                )

            return success
        except Exception as e:
            logger.error(f"❌ Error actualizando perfil: {e}")
            return False

    @staticmethod
    async def update_accessibility_preferences(user_id: str, preferences: Dict[str, Any]) -> bool:
        """Actualizar preferencias de accesibilidad"""
        try:
            update_data = {}
            for key, value in preferences.items():
                if value is not None:
                    update_data[f"accessibility.{key}"] = value

            if not update_data:
                return True

            success = await users_collection.update_user(user_id, update_data)

            if success:
                await UserService.log_accessibility_event(
                    user_id,
                    AccessibilityEventType.PREFERENCE_CHANGED,
                    {
                        "event": "accessibility_preferences_updated",
                        "preferences_changed": list(preferences.keys()),
                        "new_values": preferences
                    }
                )

            return success
        except Exception as e:
            logger.error(f"❌ Error actualizando preferencias de accesibilidad: {e}")
            return False

    @staticmethod
    async def delete_user_account(user_id: str) -> bool:
        """Eliminar cuenta de usuario"""
        try:
            await UserService.log_accessibility_event(
                user_id,
                AccessibilityEventType.PREFERENCE_CHANGED,
                {"event": "account_deleted"}
            )
            return await users_collection.delete_user(user_id)
        except Exception as e:
            logger.error(f"❌ Error eliminando cuenta: {e}")
            return False

    @staticmethod
    async def get_user_activity_log(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtener log de actividad del usuario"""
        try:
            logs = await accessibility_logs_collection.get_user_logs(user_id, limit)
            return logs
        except Exception as e:
            logger.error(f"❌ Error obteniendo logs: {e}")
            return []

    @staticmethod
    async def log_accessibility_event(
        user_id: str,
        event_type: AccessibilityEventType,
        details: Dict[str, Any]
    ):
        """Registrar evento de accesibilidad"""
        try:
            log_data = {
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "event_type": event_type.value,
                "details": details,
                "user_agent": None,
                "app_version": "1.0.0"
            }
            await accessibility_logs_collection.create_log(log_data)
        except Exception as e:
            logger.error(f"❌ Error registrando evento de accesibilidad: {e}")


user_service = UserService()