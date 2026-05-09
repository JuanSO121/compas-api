# ===== app/models/accessibility.py =====
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AccessibilityEventType(str, Enum):
    PREFERENCE_CHANGED = "preference_changed"
    ERROR_ENCOUNTERED = "error_encountered"
    FEATURE_USED = "feature_used"
    TTS_USED = "tts_used"
    VOICE_COMMAND_USED = "voice_command_used"
    NAVIGATION_ERROR = "navigation_error"


class AccessibilityLog(BaseModel):
    user_id: str = Field(..., description="ID del usuario")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: AccessibilityEventType
    details: Dict[str, Any] = Field(default_factory=dict)
    user_agent: Optional[str] = None
    app_version: Optional[str] = None


class AccessibilityPreferencesUpdate(BaseModel):
    """
    Actualización de preferencias de accesibilidad.

    Solo se incluyen los campos que efectivamente se persisten en MongoDB.
    Los campos que dependen del dispositivo (font_size, gesture_navigation,
    slow_animations, custom_notification_sounds) NO están aquí porque
    la app los maneja localmente con SharedPreferences y no deben
    sincronizarse entre dispositivos.
    """
    # Accesibilidad visual
    visual_impairment_level: Optional[str] = Field(None, pattern="^(blind|low_vision|none)$")
    screen_reader_user: Optional[bool] = None
    preferred_tts_speed: Optional[float] = Field(None, ge=0.5, le=2.0)
    high_contrast_mode: Optional[bool] = None
    dark_mode_enabled: Optional[bool] = None

    # Interacción
    haptic_feedback_enabled: Optional[bool] = None
    audio_descriptions_enabled: Optional[bool] = None
    voice_commands_enabled: Optional[bool] = None
    extended_timeout_needed: Optional[bool] = None
    audio_confirmation_enabled: Optional[bool] = None

    # Navegación
    skip_repetitive_content: Optional[bool] = None
    landmark_navigation_preferred: Optional[bool] = None

    # ── Campos REMOVIDOS (manejados localmente en el dispositivo): ────────────
    # preferred_font_size       → SharedPreferences del dispositivo
    # gesture_navigation_enabled → configuración del OS
    # slow_animations            → configuración de accesibilidad del OS
    # custom_notification_sounds → permisos del dispositivo


class DeviceCapabilities(BaseModel):
    """Capacidades detectadas del dispositivo (no se persisten en BD)"""
    has_screen_reader: bool = Field(default=False)
    supports_haptic: bool = Field(default=False)
    supports_voice_input: bool = Field(default=False)
    supports_tts: bool = Field(default=False)
    screen_size: Optional[str] = Field(None, pattern="^(small|medium|large)$")
    connection_type: Optional[str] = Field(None, pattern="^(wifi|cellular|unknown)$")
    platform: Optional[str] = Field(None, pattern="^(android|ios)$")


class VoiceCommand(BaseModel):
    command: str
    description: str
    examples: List[str] = Field(default_factory=list)
    category: str
    accessibility_level: str = Field(default="all", pattern="^(blind|low_vision|all)$")