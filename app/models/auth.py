# ===== app/models/auth.py =====
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserRegistration(BaseModel):
    """
    Registro de usuario sin contraseña.
    El sistema genera un código de acceso permanente y lo envía al email.
    Ese código es la única credencial necesaria para ingresar.
    """
    email: EmailStr = Field(..., description="Email del usuario")

    # Perfil básico opcional
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    preferred_language: str = Field(default="es", pattern="^(es|en)$")

    # Configuración inicial de accesibilidad
    visual_impairment_level: str = Field(default="none", pattern="^(blind|low_vision|none)$")
    screen_reader_user: bool = Field(default=False)


class CodeLogin(BaseModel):
    """
    Login principal: solo código de acceso permanente.
    El usuario no necesita recordar email ni contraseña.
    El código fue enviado a su correo al registrarse.
    """
    code: str = Field(
        ...,
        min_length=6,
        max_length=8,
        description="Código de acceso permanente recibido por email al registrarse"
    )


class RequestNewCode(BaseModel):
    """
    Solicitar que se reenvíe el código de acceso al correo.
    Solo requiere el email registrado — sin contraseña.
    """
    email: EmailStr = Field(..., description="Email registrado en la cuenta")


# ── Login secundario (administradores / recuperación con contraseña) ──────────
# Se mantiene por compatibilidad con usuarios que tienen password_hash guardado.

class UserLogin(BaseModel):
    """Login secundario con email y contraseña (solo admin o recuperación)"""
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=1, description="Contraseña")
    remember_me: bool = Field(default=False, description="Recordar sesión")


class PasswordReset(BaseModel):
    """Datos para reseteo de contraseña (flujo legacy)"""
    email: EmailStr = Field(..., description="Email del usuario")


class PasswordResetConfirm(BaseModel):
    """Confirmación de reseteo de contraseña"""
    token: str = Field(..., min_length=1, description="Token de reseteo")
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., description="Confirmación de contraseña")

    from pydantic import validator

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Las contraseñas no coinciden')
        return v


class TokenPair(BaseModel):
    """Par de tokens JWT"""
    access_token: str = Field(..., description="Token de acceso")
    refresh_token: str = Field(..., description="Token de renovación")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Tiempo de expiración en segundos")


class TokenRefresh(BaseModel):
    """Renovación de token"""
    refresh_token: str = Field(..., min_length=1, description="Token de renovación")