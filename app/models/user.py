# ===== app/models/user.py =====
from pydantic import BaseModel, EmailStr, Field, GetJsonSchemaHandler
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """Custom ObjectId para Pydantic v2"""

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler: GetJsonSchemaHandler) -> dict[str, Any]:
        schema = handler(schema)
        schema.update(type="string")
        return schema

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


class AccessibilityPreferences(BaseModel):
    """Preferencias de accesibilidad del usuario"""
    visual_impairment_level: str = Field(default="none", pattern="^(blind|low_vision|none)$")
    screen_reader_user: bool = Field(default=False)
    preferred_tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    preferred_font_size: str = Field(default="medium", pattern="^(small|medium|large|x-large)$")
    high_contrast_mode: bool = Field(default=False)
    dark_mode_enabled: bool = Field(default=False)

    # Preferencias de interacción
    haptic_feedback_enabled: bool = Field(default=True)
    audio_descriptions_enabled: bool = Field(default=False)
    voice_commands_enabled: bool = Field(default=False)
    gesture_navigation_enabled: bool = Field(default=True)

    # Configuraciones de tiempo
    extended_timeout_needed: bool = Field(default=False)
    slow_animations: bool = Field(default=False)

    # Sonidos y audio
    custom_notification_sounds: bool = Field(default=False)
    audio_confirmation_enabled: bool = Field(default=True)

    # Navegación
    skip_repetitive_content: bool = Field(default=True)
    landmark_navigation_preferred: bool = Field(default=True)


class UserProfile(BaseModel):
    """Perfil básico del usuario"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    date_of_birth: Optional[datetime] = None
    preferred_language: str = Field(default="es", pattern="^(es|en)$")
    timezone: str = Field(default="America/Bogota")


class SecurityQuestion(BaseModel):
    """Pregunta de seguridad"""
    question: str = Field(..., min_length=10, max_length=200)
    answer_hash: str = Field(..., min_length=1)


class UserSecurity(BaseModel):
    """Configuraciones de seguridad del usuario"""
    login_attempts: int = Field(default=0)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    account_locked_until: Optional[datetime] = None

    # ─────────────────────────────────────────────────
    # CÓDIGO DE ACCESO PERMANENTE (LOGIN PRINCIPAL)
    # ─────────────────────────────────────────────────
    # Este código se genera al registrarse y se envía al correo.
    # Es la única credencial necesaria para iniciar sesión.
    # Se puede regenerar usando email + contraseña (recuperación).
    permanent_access_code: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=8,
        description="Código permanente de acceso para login sin contraseña"
    )
    # Fecha en que se usó el código por primera vez (= verificación de cuenta)
    permanent_code_first_used_at: Optional[datetime] = Field(
        default=None,
        description="Fecha del primer login con código (verificación de cuenta)"
    )
    # Historial de regeneraciones del código (para auditoría)
    code_regenerated_at: Optional[datetime] = Field(
        default=None,
        description="Última vez que se generó un nuevo código"
    )

    # ─────────────────────────────────────────────────
    # VERIFICACIÓN DE EMAIL (mantenido por compatibilidad)
    # ─────────────────────────────────────────────────
    email_verification_code: Optional[Any] = Field(
        default=None,
        description="Código temporal de verificación (legacy)"
    )
    email_verification_expires: Optional[datetime] = Field(default=None)
    email_verification_attempts: int = Field(default=0)
    email_verified_at: Optional[datetime] = Field(default=None)
    verification_skipped_at: Optional[datetime] = Field(default=None)

    # ─────────────────────────────────────────────────
    # RESETEO DE CONTRASEÑA (sin cambios)
    # ─────────────────────────────────────────────────
    password_reset_tokens: List[Dict[str, Any]] = Field(default_factory=list)

    # Configuraciones accesibles
    biometric_enabled: bool = Field(default=False)
    two_factor_method: str = Field(default="none", pattern="^(none|email|sms)$")
    security_questions: List[SecurityQuestion] = Field(default_factory=list, max_items=3)


class User(BaseModel):
    """Modelo de usuario"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr = Field(..., description="Email único del usuario")
    password_hash: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)  # Se vuelve True en el primer login con código

    # Componentes del perfil
    profile: UserProfile = Field(default_factory=UserProfile)
    accessibility: AccessibilityPreferences = Field(default_factory=AccessibilityPreferences)
    security: UserSecurity = Field(default_factory=UserSecurity)

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "profile": {
                    "first_name": "Juan",
                    "last_name": "Pérez",
                    "preferred_language": "es",
                    "timezone": "America/Bogota"
                },
                "accessibility": {
                    "visual_impairment_level": "blind",
                    "screen_reader_user": True,
                    "preferred_tts_speed": 1.2,
                    "high_contrast_mode": True
                }
            }
        }