# ===== app/services/auth_service.py =====
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.database.collections import users_collection
from app.models.auth import TokenPair
import secrets
import logging
import bcrypt as _bcrypt

logger = logging.getLogger(__name__)

# Configurar encriptación de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """Servicio de autenticación"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hashear contraseña"""
        salt = _bcrypt.gensalt(rounds=12)
        hashed = _bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verificar contraseña"""
        try:
            return _bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Error verificando password: {e}")
            return False
        
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Crear token de acceso"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Crear token de renovación"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_token_pair(user_data: Dict[str, Any]) -> TokenPair:
        """Crear par de tokens"""
        token_data = {
            "sub": str(user_data["_id"]),
            "email": user_data["email"],
            "accessibility_level": user_data.get("accessibility", {}).get("visual_impairment_level", "none")
        }
        
        access_token = AuthService.create_access_token(token_data)
        refresh_token = AuthService.create_refresh_token(token_data)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    @staticmethod
    async def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verificar token JWT"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            
            if payload.get("type") != token_type:
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                return None
            
            # Verificar que el usuario existe
            user = await users_collection.find_user_by_id(user_id)
            if not user or not user.get("is_active"):
                return None
            
            return payload
            
        except JWTError as e:
            logger.error(f"Error verificando token: {e}")
            return None
    
    @staticmethod
    def generate_verification_token() -> str:
        """Generar token de verificación"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Autenticar usuario"""
        try:
            user = await users_collection.find_user_by_email(email)
            
            if not user:
                return None
            
            # Verificar si la cuenta está bloqueada
            locked_until = user.get("security", {}).get("account_locked_until")
            if locked_until and locked_until > datetime.utcnow():
                return None
            
            # Verificar contraseña
            if not AuthService.verify_password(password, user["password_hash"]):
                # Incrementar intentos fallidos
                await users_collection.update_login_attempts(email, increment=True)
                
                # Verificar si debe bloquear la cuenta
                failed_attempts = user.get("security", {}).get("failed_login_attempts", 0) + 1
                if failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                    await users_collection.lock_account(email, settings.LOCKOUT_DURATION_MINUTES)
                
                return None
            
            # Login exitoso - resetear intentos fallidos
            await users_collection.update_login_attempts(email, increment=False)
            
            return user
            
        except Exception as e:
            logger.error(f" Error autenticando usuario: {e}")
            return None

auth_service = AuthService()
