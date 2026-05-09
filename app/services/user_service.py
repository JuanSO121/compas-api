# ===== app/services/user_service.py =====
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.database.collections import users_collection, accessibility_logs_collection
from app.models.accessibility import AccessibilityEventType
import logging

logger = logging.getLogger(__name__)


class UserService:

    @staticmethod
    async def create_user(user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crear nuevo usuario sin contraseña.

        El dict recibido ya trae password_hash="" desde el endpoint de registro.
        Esta función genera el código de acceso permanente y lo añade al documento.
        NO hashea ninguna contraseña — eso ya no es parte del flujo de registro.
        """
        try:
            existing_user = await users_collection.find_user_by_email(user_data["email"])
            if existing_user:
                logger.warning(f"⚠️ Email ya existe: {user_data['email']}")
                return None

            # Generar código de acceso permanente
            from app.services.verification_service import verification_service
            permanent_code = await verification_service.generate_unique_access_code()

            if "security" not in user_data:
                user_data["security"] = {}

            user_data["security"]["permanent_access_code"] = permanent_code
            user_data["security"]["code_regenerated_at"] = datetime.utcnow()
            user_data["is_active"] = True
            user_data["is_verified"] = False

            user = await users_collection.create_user(user_data)

            await UserService.log_accessibility_event(
                str(user["_id"]),
                AccessibilityEventType.PREFERENCE_CHANGED,
                {
                    "event": "user_registered",
                    "accessibility_level": user_data.get("accessibility", {}).get(
                        "visual_impairment_level", "none"
                    )
                }
            )

            logger.info(f"✅ Usuario creado: {user['email']}")
            return user

        except Exception as e:
            logger.error(f"❌ Error creando usuario: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
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
        try:
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
    async def update_accessibility_preferences(
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Actualiza preferencias de accesibilidad en BD.

        Solo se permiten los campos definidos en AccessibilityPreferences del modelo.
        Los campos de dispositivo (font_size, gesture_navigation, etc.) son ignorados
        aunque lleguen — no se guardan en BD.
        """
        # Campos permitidos en BD (los del modelo AccessibilityPreferences)
        ALLOWED_FIELDS = {
            "visual_impairment_level",
            "screen_reader_user",
            "preferred_tts_speed",
            "high_contrast_mode",
            "dark_mode_enabled",
            "haptic_feedback_enabled",
            "audio_descriptions_enabled",
            "voice_commands_enabled",
            "extended_timeout_needed",
            "audio_confirmation_enabled",
            "skip_repetitive_content",
            "landmark_navigation_preferred",
        }

        try:
            update_data = {}
            skipped = []
            for key, value in preferences.items():
                if value is None:
                    continue
                if key in ALLOWED_FIELDS:
                    update_data[f"accessibility.{key}"] = value
                else:
                    skipped.append(key)

            if skipped:
                logger.info(
                    f"ℹ️ Campos de dispositivo ignorados (no se guardan en BD): {skipped}"
                )

            if not update_data:
                return True

            success = await users_collection.update_user(user_id, update_data)

            if success:
                await UserService.log_accessibility_event(
                    user_id,
                    AccessibilityEventType.PREFERENCE_CHANGED,
                    {
                        "event": "accessibility_preferences_updated",
                        "preferences_changed": list(
                            k.replace("accessibility.", "") for k in update_data.keys()
                        ),
                        "device_only_skipped": skipped
                    }
                )
            return success
        except Exception as e:
            logger.error(f"❌ Error actualizando preferencias: {e}")
            return False

    @staticmethod
    async def delete_user_account(user_id: str) -> bool:
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
        try:
            return await accessibility_logs_collection.get_user_logs(user_id, limit)
        except Exception as e:
            logger.error(f"❌ Error obteniendo logs: {e}")
            return []

    @staticmethod
    async def log_accessibility_event(
        user_id: str,
        event_type: AccessibilityEventType,
        details: Dict[str, Any]
    ):
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
            logger.error(f"❌ Error registrando evento: {e}")


user_service = UserService()