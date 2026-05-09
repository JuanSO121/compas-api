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
    """
    Preferencias de accesibilidad del usuario.

    NOTA SOBRE QUÉ SE PERSISTE EN BD:
    - Los campos aquí definidos se guardan en MongoDB y se restauran
      al iniciar sesión desde cualquier dispositivo.
    - Preferencias de UI puras que dependen del dispositivo (tamaño de
      pantalla, brillo, etc.) NO deben guardarse aquí — esas van en
      SharedPreferences / almacenamiento local del dispositivo.
    - Los campos marcados como "interno app" son leídos por el backend
      para lógica de negocio (rate limiting, timeouts) pero también
      se envían al cliente para que la app configure su comportamiento.
    """

    # ── Accesibilidad visual — persiste en BD ─────────────────────────────────
    visual_impairment_level: str = Field(
        default="none",
        pattern="^(blind|low_vision|none)$",
        description="Nivel de discapacidad visual. Afecta rate limiting y timeouts del backend."
    )
    screen_reader_user: bool = Field(
        default=False,
        description="Indica si usa lector de pantalla. Usado por backend para mensajes TTS."
    )
    preferred_tts_speed: float = Field(
        default=1.0, ge=0.5, le=2.0,
        description="Velocidad preferida de síntesis de voz. Persiste entre dispositivos."
    )
    high_contrast_mode: bool = Field(
        default=False,
        description="Modo de alto contraste. Persiste entre dispositivos."
    )
    dark_mode_enabled: bool = Field(
        default=False,
        description="Modo oscuro. Persiste entre dispositivos."
    )

    # ── Interacción — persiste en BD ──────────────────────────────────────────
    haptic_feedback_enabled: bool = Field(
        default=True,
        description="Retroalimentación háptica. Persiste entre dispositivos."
    )
    audio_descriptions_enabled: bool = Field(
        default=False,
        description="Descripciones de audio para contenido visual. Persiste en BD."
    )
    voice_commands_enabled: bool = Field(
        default=False,
        description="Comandos de voz habilitados. Persiste en BD."
    )
    extended_timeout_needed: bool = Field(
        default=False,
        description=(
            "El usuario necesita más tiempo para interacciones. "
            "Usado por backend para extender rate limiting y timeouts de sesión."
        )
    )
    audio_confirmation_enabled: bool = Field(
        default=True,
        description="Confirmaciones de audio en acciones. Persiste en BD."
    )

    # ── Navegación — persiste en BD ───────────────────────────────────────────
    skip_repetitive_content: bool = Field(
        default=True,
        description="Saltar contenido repetitivo (para lectores de pantalla)."
    )
    landmark_navigation_preferred: bool = Field(
        default=True,
        description="Preferencia de navegación por landmarks de accesibilidad."
    )

    # ── Campos que NO se guardan en BD (manejados localmente en el dispositivo):
    # - preferred_font_size  → depende de la pantalla del dispositivo
    # - gesture_navigation_enabled → depende del OS y configuración del dispositivo
    # - slow_animations → depende de la configuración de accesibilidad del OS
    # - custom_notification_sounds → depende de los permisos del dispositivo
    # Estos campos se removieron del modelo de BD intencionalmente.
    # La app los maneja con SharedPreferences y los lee del sistema operativo.


class UserProfile(BaseModel):
    """Perfil básico del usuario — todo persiste en BD"""
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
    last_login: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    account_locked_until: Optional[datetime] = None

    # ── Código de acceso permanente (login principal) ─────────────────────────
    permanent_access_code: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=8,
        description="Código permanente de acceso para login sin contraseña"
    )
    permanent_code_first_used_at: Optional[datetime] = Field(
        default=None,
        description="Fecha del primer login con código (= verificación de cuenta)"
    )
    code_regenerated_at: Optional[datetime] = Field(
        default=None,
        description="Última vez que se generó un nuevo código"
    )

    # ── Verificación de email (campos legacy — se mantienen para compatibilidad) ──
    email_verification_code: Optional[Any] = Field(default=None)
    email_verification_expires: Optional[datetime] = Field(default=None)
    email_verification_attempts: int = Field(default=0)
    email_verified_at: Optional[datetime] = Field(default=None)
    verification_skipped_at: Optional[datetime] = Field(default=None)

    # ── Reseteo de contraseña (legacy — para usuarios con password_hash) ──────
    password_reset_tokens: List[Dict[str, Any]] = Field(default_factory=list)

    # ── Biometría y 2FA ───────────────────────────────────────────────────────
    biometric_enabled: bool = Field(default=False)
    two_factor_method: str = Field(default="none", pattern="^(none|email|sms)$")
    security_questions: List[SecurityQuestion] = Field(default_factory=list, max_items=3)


class User(BaseModel):
    """
    Modelo de usuario.

    password_hash es opcional porque los nuevos usuarios se registran
    sin contraseña. Los usuarios legacy (registrados antes del cambio)
    mantienen su hash — esto permite que el login secundario
    email+contraseña siga funcionando para ellos.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr = Field(..., description="Email único del usuario")

    # Opcional: vacío ("") en usuarios nuevos, hash real en usuarios legacy.
    password_hash: str = Field(
        default="",
        description="Hash bcrypt. Vacío en usuarios sin contraseña."
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)

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