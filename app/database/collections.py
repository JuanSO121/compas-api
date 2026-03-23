# ===== app/database/collections.py =====
from app.database.connection import get_database
from app.models.user import User
from app.models.accessibility import AccessibilityLog
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class UsersCollection:
    """Operaciones de la colección users"""

    def __init__(self):
        self.collection = None

    def get_collection(self):
        if self.collection is None:
            db = get_database()
            self.collection = db.users
        return self.collection

    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crear nuevo usuario"""
        try:
            collection = self.get_collection()
            result = await collection.insert_one(user_data)

            if result.inserted_id:
                user_data["_id"] = result.inserted_id
                logger.info(f"✅ Usuario creado: {user_data.get('email')}")
                return user_data
            else:
                raise Exception("No se pudo crear el usuario")

        except Exception as e:
            logger.error(f"❌ Error creando usuario: {e}")
            raise e

    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Buscar usuario por email"""
        try:
            collection = self.get_collection()
            user = await collection.find_one({"email": email})
            return user
        except Exception as e:
            logger.error(f"❌ Error buscando usuario por email: {e}")
            return None

    async def find_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Buscar usuario por ID"""
        try:
            collection = self.get_collection()
            user = await collection.find_one({"_id": ObjectId(user_id)})
            return user
        except Exception as e:
            logger.error(f"❌ Error buscando usuario por ID: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # NUEVO: Buscar usuario por código de acceso permanente
    # Este es el método central del nuevo flujo de login por código.
    # ─────────────────────────────────────────────────────────────────
    async def find_user_by_access_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Buscar usuario por su código de acceso permanente.
        Se usa en el endpoint /login-with-code.
        """
        try:
            collection = self.get_collection()
            user = await collection.find_one({
                "security.permanent_access_code": code,
                "is_active": {"$ne": False}
            })
            return user
        except Exception as e:
            logger.error(f"❌ Error buscando usuario por código de acceso: {e}")
            return None

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Actualizar usuario"""
        try:
            collection = self.get_collection()
            update_data["updated_at"] = datetime.utcnow()

            result = await collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )

            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Error actualizando usuario: {e}")
            return False

    async def delete_user(self, user_id: str) -> bool:
        """Eliminar usuario"""
        try:
            collection = self.get_collection()
            result = await collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"❌ Error eliminando usuario: {e}")
            return False

    async def update_login_attempts(self, email: str, increment: bool = True) -> bool:
        """Actualizar intentos de login"""
        try:
            collection = self.get_collection()

            if increment:
                result = await collection.update_one(
                    {"email": email},
                    {
                        "$inc": {"security.failed_login_attempts": 1},
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
            else:
                result = await collection.update_one(
                    {"email": email},
                    {
                        "$set": {
                            "security.failed_login_attempts": 0,
                            "security.last_login": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Error actualizando intentos de login: {e}")
            return False

    async def lock_account(self, email: str, duration_minutes: int = 15) -> bool:
        """Bloquear cuenta por intentos fallidos"""
        try:
            collection = self.get_collection()
            lock_until = datetime.utcnow() + timedelta(minutes=duration_minutes)

            result = await collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "security.account_locked_until": lock_until,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Error bloqueando cuenta: {e}")
            return False

    async def find_user_by_email_verification_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Buscar usuario por token de verificación de email (legacy)"""
        try:
            collection = self.get_collection()
            user = await collection.find_one({
                "security.email_verification_token": token
            })
            return user
        except Exception as e:
            logger.error(f"❌ Error buscando usuario por token de verificación: {e}")
            return None


class AccessibilityLogsCollection:
    """Operaciones de la colección accessibility_logs"""

    def __init__(self):
        self.collection = None

    def get_collection(self):
        if self.collection is None:
            db = get_database()
            self.collection = db.accessibility_logs
        return self.collection

    async def create_log(self, log_data: Dict[str, Any]) -> bool:
        """Crear log de accesibilidad"""
        try:
            collection = self.get_collection()
            await collection.insert_one(log_data)
            return True
        except Exception as e:
            logger.error(f"❌ Error creando log de accesibilidad: {e}")
            return False

    async def get_user_logs(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtener logs de un usuario"""
        try:
            collection = self.get_collection()
            cursor = collection.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit)

            logs = await cursor.to_list(length=limit)
            return logs
        except Exception as e:
            logger.error(f"❌ Error obteniendo logs: {e}")
            return []


# Instancias globales
users_collection = UsersCollection()
accessibility_logs_collection = AccessibilityLogsCollection()