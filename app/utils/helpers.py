# ===== app/utils/helpers.py =====
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import secrets
import string

class AccessibleHelpers:
    """Utilidades helper para funcionalidad accesible"""
    
    @staticmethod
    def create_accessible_response(
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[Dict[str, str]]] = None,
        accessibility_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Crear respuesta estructurada accesible"""
        
        # ✅ FIX: Determinar tipo de mensaje correctamente.
        # Antes, success=False sin errors[] retornaba message_type="info",
        # lo que era semánticamente incorrecto (ej: token inválido devolvía "info").
        if success:
            message_type = "success"
            haptic_pattern = "success"
        else:
            message_type = "error"
            haptic_pattern = "error"
        
        # Información de accesibilidad por defecto
        default_accessibility = {
            "announcement": message,
            "focus_element": None,
            "haptic_pattern": haptic_pattern
        }
        
        if accessibility_info:
            default_accessibility.update(accessibility_info)
        
        response = {
            "success": success,
            "message": message,
            "message_type": message_type,
            "data": data or {},
            "accessibility_info": default_accessibility,
            "errors": errors or [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return response
    
    @staticmethod
    def create_accessible_error(
        message: str,
        field: str = "general",
        suggestion: Optional[str] = None
    ) -> Dict[str, Any]:
        """Crear error accesible con sugerencia"""
        return {
            "field": field,
            "message": message,
            "suggestion": suggestion or "Verifique la información e intente nuevamente"
        }
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generar token seguro"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_numeric_code(length: int = 6) -> str:
        """Generar código numérico para 2FA"""
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    @staticmethod
    def sanitize_user_input(input_str: str) -> str:
        """Sanitizar entrada de usuario manteniendo accesibilidad"""
        if not input_str:
            return ""
        
        # Limpiar espacios extra pero mantener espacios necesarios para TTS
        cleaned = ' '.join(input_str.split())
        
        # Remover caracteres potencialmente peligrosos
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
        for char in dangerous_chars:
            cleaned = cleaned.replace(char, '')
        
        return cleaned.strip()
    
    @staticmethod
    def format_datetime_accessible(dt: datetime) -> str:
        """Formatear fecha/hora de manera accesible para TTS"""
        return dt.strftime("%d de %B de %Y a las %I:%M %p")
    
    @staticmethod
    def calculate_accessibility_score(user_data: Dict[str, Any]) -> int:
        """Calcular puntuación de necesidades de accesibilidad"""
        accessibility = user_data.get("accessibility", {})
        score = 0
        
        # Discapacidad visual (peso alto)
        if accessibility.get("visual_impairment_level") == "blind":
            score += 10
        elif accessibility.get("visual_impairment_level") == "low_vision":
            score += 7
        
        # Usuario de lector de pantalla
        if accessibility.get("screen_reader_user"):
            score += 8
        
        # Otras necesidades
        if accessibility.get("extended_timeout_needed"):
            score += 3
        if accessibility.get("voice_commands_enabled"):
            score += 2
        if accessibility.get("haptic_feedback_enabled"):
            score += 1
        
        return min(score, 20)  # Máximo 20 puntos