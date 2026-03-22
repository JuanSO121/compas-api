# ===== app/services/email_service.py =====
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio de email usando Gmail SMTP gratuito"""

    @staticmethod
    def create_smtp_connection():
        """Crear conexión SMTP"""
        try:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            return server
        except Exception as e:
            logger.error(f"❌ Error conectando a SMTP: {e}")
            return None

    @staticmethod
    async def send_email(
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Enviar email"""
        try:
            server = EmailService.create_smtp_connection()
            if not server:
                return False

            msg = MIMEMultipart('alternative')
            msg['From'] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
            msg['To'] = ", ".join(to_emails)
            msg['Subject'] = subject

            if text_content:
                msg.attach(MIMEText(text_content, 'plain', 'utf-8'))

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            server.sendmail(settings.FROM_EMAIL, to_emails, msg.as_string())
            server.quit()

            logger.info(f"✅ Email enviado exitosamente a {to_emails}")
            return True

        except Exception as e:
            logger.error(f"❌ Error enviando email: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    # NUEVO: Email con código de acceso PERMANENTE
    # Este es el email principal del sistema.
    # Se envía al registrarse y cuando el usuario pide un nuevo código.
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    async def send_permanent_access_code_email(
        email: str,
        code: str,
        user_name: str = "",
        is_regenerated: bool = False  # True = el usuario pidió un nuevo código
    ) -> bool:
        """
        Enviar email con el código de acceso permanente.
        El código NO tiene fecha de vencimiento - el usuario lo guarda y usa siempre.
        """
        greeting = f"Hola{f' {user_name}' if user_name else ''}"

        if is_regenerated:
            subject = "Tu nuevo código de acceso - App Accesible"
            action_text = "Tu código de acceso ha sido renovado. Guarda este nuevo código."
            intro_text = (
                "Recibimos tu solicitud para generar un nuevo código de acceso. "
                "A partir de ahora, usa este código para ingresar a la aplicación. "
                "El código anterior ya no funciona."
            )
        else:
            subject = "Tu código de acceso permanente - App Accesible"
            action_text = "¡Tu cuenta está lista! Este es tu código de acceso."
            intro_text = (
                "Gracias por registrarte. "
                "Este código es tu llave de acceso permanente a la aplicación. "
                "No tiene fecha de vencimiento."
            )

        # Código espaciado para lectores de pantalla (TTS lo lee dígito por dígito)
        spaced_code = "  ".join(code)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.8; color: #1a1a1a; background: #f5f5f5; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; }}
                .header {{ background: #1d4ed8; color: white; padding: 32px 24px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ padding: 32px 24px; }}
                .code-box {{
                    background: #1e3a8a;
                    border-radius: 16px;
                    padding: 36px 24px;
                    text-align: center;
                    margin: 32px 0;
                }}
                .code-label {{
                    color: #93c5fd;
                    font-size: 14px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 3px;
                    margin-bottom: 16px;
                }}
                .code {{
                    font-family: 'Courier New', Courier, monospace;
                    font-size: 56px;
                    font-weight: 900;
                    color: #ffffff;
                    letter-spacing: 16px;
                    display: block;
                    margin: 16px 0;
                }}
                .code-permanent-badge {{
                    background: #16a34a;
                    color: white;
                    padding: 6px 18px;
                    border-radius: 999px;
                    font-size: 13px;
                    font-weight: 700;
                    display: inline-block;
                    margin-top: 12px;
                }}
                .tts-box {{
                    background: #eff6ff;
                    border-left: 5px solid #1d4ed8;
                    padding: 20px;
                    margin: 24px 0;
                    border-radius: 0 8px 8px 0;
                }}
                .tts-box h3 {{ margin-top: 0; color: #1d4ed8; font-size: 15px; }}
                .tts-code {{
                    font-size: 28px;
                    font-weight: 700;
                    letter-spacing: 10px;
                    color: #1e3a8a;
                    font-family: 'Courier New', monospace;
                }}
                .warning-box {{
                    background: #fefce8;
                    border-left: 5px solid #ca8a04;
                    padding: 20px;
                    margin: 24px 0;
                    border-radius: 0 8px 8px 0;
                }}
                .warning-box h3 {{ margin-top: 0; color: #92400e; font-size: 15px; }}
                .how-to-use {{
                    background: #f0fdf4;
                    border-left: 5px solid #16a34a;
                    padding: 20px;
                    margin: 24px 0;
                    border-radius: 0 8px 8px 0;
                }}
                .how-to-use h3 {{ margin-top: 0; color: #166534; font-size: 15px; }}
                p {{ margin: 0 0 16px; font-size: 16px; }}
                ul {{ padding-left: 24px; margin: 0; }}
                li {{ margin-bottom: 10px; font-size: 15px; }}
                .footer {{ background: #f1f5f9; padding: 20px 24px; text-align: center; color: #64748b; font-size: 13px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔑 Código de Acceso Permanente</h1>
                </div>

                <div class="content">
                    <p>{greeting},</p>
                    <p>{intro_text}</p>

                    <!-- CÓDIGO PRINCIPAL -->
                    <div class="code-box" role="region" aria-label="Tu código de acceso">
                        <div class="code-label">Tu código de acceso es:</div>
                        <span class="code" aria-label="Código: {spaced_code}">{code}</span>
                        <div class="code-permanent-badge">✓ CÓDIGO PERMANENTE — NO VENCE</div>
                    </div>

                    <!-- PARA LECTORES DE PANTALLA -->
                    <div class="tts-box" role="complementary" aria-label="Información para usuarios de lectores de pantalla">
                        <h3>🔊 Para usuarios de lector de pantalla</h3>
                        <p style="margin-bottom: 8px;">El código leído dígito por dígito es:</p>
                        <div class="tts-code" aria-label="{spaced_code}">{spaced_code}</div>
                    </div>

                    <!-- CÓMO USARLO -->
                    <div class="how-to-use">
                        <h3>✅ Cómo ingresar a la aplicación</h3>
                        <ul>
                            <li>Abre la aplicación y ve a "Iniciar sesión"</li>
                            <li>Escribe tu código de acceso: <strong>{code}</strong></li>
                            <li>¡Listo! No necesitas email ni contraseña para entrar</li>
                        </ul>
                    </div>

                    <!-- ADVERTENCIAS -->
                    <div class="warning-box" role="alert">
                        <h3>⚠️ Guarda este código en un lugar seguro</h3>
                        <ul>
                            <li><strong>No lo compartas con nadie</strong> — es la llave de tu cuenta</li>
                            <li>Guárdalo en un lugar donde puedas encontrarlo fácilmente</li>
                            <li>Si lo pierdes, puedes pedir uno nuevo desde la app usando tu email y contraseña</li>
                            {'<li><strong>Tu código anterior ya no funciona</strong>, usa únicamente este nuevo código</li>' if is_regenerated else ''}
                        </ul>
                    </div>
                </div>

                <div class="footer">
                    <p>Si no creaste esta cuenta, ignora este email.</p>
                    <p>App Accesible — Diseñada para todos</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
{'='*50}
CÓDIGO DE ACCESO PERMANENTE
{'='*50}

{greeting},

{intro_text}

{'='*50}
TU CÓDIGO DE ACCESO ES:

    {code}

Leído dígito por dígito: {spaced_code}

ESTE CÓDIGO NO VENCE
{'='*50}

CÓMO USARLO:
- Abre la aplicación
- Ve a "Iniciar sesión"
- Escribe el código: {code}
- ¡Listo! No necesitas email ni contraseña

IMPORTANTE:
- Guarda este código en un lugar seguro
- No lo compartas con nadie
- Si lo pierdes, pide uno nuevo con tu email y contraseña
{'- Tu código anterior ya dejó de funcionar' if is_regenerated else ''}

Si no creaste esta cuenta, ignora este email.
        """

        return await EmailService.send_email([email], subject, html_content, text_content)

    # ─────────────────────────────────────────────────────────────────────
    # MÉTODOS EXISTENTES (sin cambios)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    async def send_verification_code_email(
        email: str,
        code: str,
        user_name: str = "",
        expires_minutes: int = 15
    ) -> bool:
        """Enviar email con código temporal de verificación (legacy)"""
        subject = "Código de Verificación - App Accesible"
        spaced_code = ' '.join(code)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>{subject}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2563eb; color: white; padding: 30px 20px; text-align: center; border-radius: 12px 12px 0 0; }}
                .code-container {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 16px; margin: 30px 0; }}
                .verification-code {{ font-size: 48px; font-weight: bold; color: white; letter-spacing: 12px; font-family: 'Courier New', monospace; }}
                .accessible-info {{ background-color: #f0f9ff; padding: 20px; margin: 20px 0; border-left: 4px solid #2563eb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h1>🔐 Código de Verificación</h1></div>
                <div style="padding: 30px;">
                    <p>Hola{"" if not user_name else f" {user_name}"},</p>
                    <div class="code-container">
                        <div style="color:white;font-size:18px;margin-bottom:10px;">TU CÓDIGO ES:</div>
                        <div class="verification-code">{code}</div>
                        <p style="color:white;margin-top:15px;">⏱️ Válido por {expires_minutes} minutos</p>
                    </div>
                    <div class="accessible-info">
                        <h3 style="color:#2563eb;">🔊 Para lectores de pantalla:</h3>
                        <p>El código es: <strong style="font-size:18px;letter-spacing:4px;">{spaced_code}</strong></p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
Código de Verificación

Hola{"" if not user_name else f" {user_name}"},

Tu código de verificación es: {code}
Espaciado: {spaced_code}

Válido por {expires_minutes} minutos. Tienes 5 intentos.
No compartas este código con nadie.
        """

        return await EmailService.send_email([email], subject, html_content, text_content)

    @staticmethod
    async def send_verification_email(email: str, token: str, user_name: str = "") -> bool:
        """Enviar email de verificación por enlace (legacy)"""
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        subject = "Verificación de cuenta - App Accesible"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="es"><head><meta charset="UTF-8"><title>{subject}</title></head>
        <body style="font-family:Arial,sans-serif;color:#333;">
            <h1>¡Bienvenido{"" if not user_name else f", {user_name}"}!</h1>
            <p>Verifica tu cuenta haciendo clic en el enlace:</p>
            <a href="{verification_url}" style="background:#16a34a;color:white;padding:15px 30px;text-decoration:none;border-radius:5px;">Verificar Mi Cuenta</a>
            <p>O copia: {verification_url}</p>
            <p><small>Expira en 24 horas.</small></p>
        </body></html>
        """

        text_content = f"Verifica tu cuenta: {verification_url}\nExpira en 24 horas."
        return await EmailService.send_email([email], subject, html_content, text_content)

    @staticmethod
    async def send_password_reset_email(email: str, token: str, user_name: str = "") -> bool:
        """Enviar email de reseteo de contraseña"""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "Reseteo de Contraseña - App Accesible"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="es"><head><meta charset="UTF-8"><title>{subject}</title></head>
        <body style="font-family:Arial,sans-serif;color:#333;">
            <h1 style="color:#dc2626;">Reseteo de Contraseña</h1>
            <p>Hola{"" if not user_name else f" {user_name}"},</p>
            <p>Recibimos una solicitud para resetear tu contraseña.</p>
            <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:15px;margin:20px 0;">
                <strong>⚠️ Solo haz clic si solicitaste el reseteo.</strong>
            </div>
            <a href="{reset_url}" style="background:#dc2626;color:white;padding:15px 30px;text-decoration:none;border-radius:5px;">Resetear Mi Contraseña</a>
            <p>O copia: {reset_url}</p>
            <p><small>Expira en 1 hora.</small></p>
        </body></html>
        """

        text_content = f"""
Reseteo de Contraseña

Hola{"" if not user_name else f" {user_name}"},
Enlace para resetear contraseña: {reset_url}
Expira en 1 hora. Si no lo solicitaste, ignora este email.
        """

        return await EmailService.send_email([email], subject, html_content, text_content)


email_service = EmailService()