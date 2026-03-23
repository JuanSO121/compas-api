# COMPAS API

API desarrollada con FastAPI para una aplicación accesible orientada a personas ciegas y con baja visión. El proyecto prioriza respuestas compatibles con lectores de pantalla, mensajes descriptivos y un flujo de autenticación adaptado a accesibilidad.

## Características principales

- **FastAPI + Vercel**: la app puede ejecutarse localmente con Uvicorn o desplegarse en Vercel usando `api/index.py` como entrypoint ASGI.
- **MongoDB Atlas**: almacenamiento principal mediante `motor`/`pymongo`.
- **Autenticación accesible**: registro con email + contraseña y login principal mediante **código permanente** de acceso enviado por correo.
- **Respuestas accesibles**: estructura estándar con `success`, `message`, `data`, `accessibility_info`, `errors` y `timestamp`.
- **Headers de accesibilidad**: todas las respuestas exponen headers específicos para clientes accesibles.
- **Preferencias de accesibilidad**: soporte para configuraciones como lector de pantalla, contraste, velocidad TTS y timeouts extendidos.
- **Rate limiting inclusivo**: el servicio de seguridad flexibiliza límites para usuarios con necesidades de accesibilidad.

## Estructura del proyecto

```text
.
├── api/
│   └── index.py              # Entry point ASGI para Vercel
├── app/
│   ├── config/               # Settings y configuración
│   ├── database/             # Conexión e índices de MongoDB
│   ├── middleware/           # Manejo de errores y middlewares
│   ├── models/               # Modelos Pydantic
│   ├── routes/               # Endpoints de la API
│   ├── services/             # Lógica de autenticación, email y seguridad
│   └── utils/                # Helpers, constantes y validadores
├── tests/                    # Tests automatizados
├── README.md
├── requirements.txt
└── vercel.json
```

## Requisitos

- Python 3.10 o superior recomendado.
- Una base MongoDB accesible desde la API.
- Un servidor SMTP válido para el envío de códigos y correos transaccionales.

## Instalación local

```bash
git clone <tu-repo>
cd compas-api
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Variables de entorno

El proyecto carga configuración desde `.env` usando `pydantic-settings`. Actualmente **no existe un `.env.example` en el repositorio**, así que debes crear el archivo manualmente.

Variables requeridas:

```env
DATABASE_URL=mongodb+srv://<usuario>:<password>@<cluster>/<db>
DATABASE_NAME=compas

JWT_SECRET_KEY=una-clave-segura
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu_correo@example.com
SMTP_PASSWORD=tu_password_o_app_password
FROM_EMAIL=tu_correo@example.com
FROM_NAME=COMPAS

ALLOWED_ORIGINS=["http://localhost:3000"]

BCRYPT_ROUNDS=12
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15

REDIS_URL=redis://localhost:6379/0
USE_REDIS=false

FRONTEND_URL=http://localhost:3000
```

### Notas de configuración

- `ALLOWED_ORIGINS` debe enviarse como lista JSON válida.
- Aunque existen `REDIS_URL` y `USE_REDIS`, el control de rate limiting actual se mantiene en memoria.
- En desarrollo, `SMTP_HOST`/`SMTP_PORT` pueden apuntar a un servicio de testing de correo si no quieres usar Gmail.

## Ejecución en local

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Si todo está correcto, la API quedará disponible en:

- `http://localhost:8000/`
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Flujo de autenticación actual

El README anterior quedó desactualizado porque el proyecto ya no depende únicamente del login clásico por email/contraseña. Hoy conviven dos flujos:

### 1. Registro

`POST /api/v1/auth/register`

- El usuario se registra con email y contraseña.
- Al crear la cuenta, el backend genera un **código de acceso permanente**.
- Ese código se envía por correo y pasa a ser la credencial principal para iniciar sesión.

### 2. Login principal con código

`POST /api/v1/auth/login-with-code`

- Es el flujo principal de acceso.
- Solo requiere el código numérico recibido por email.
- En el primer login puede marcar la cuenta como verificada automáticamente.

### 3. Regenerar código

`POST /api/v1/auth/request-new-code`

- Si el usuario pierde el código, puede solicitar uno nuevo.
- Este flujo sí valida identidad con email + contraseña.

### 4. Login clásico complementario

`POST /api/v1/auth/login`

- Sigue existiendo como flujo secundario / legado.
- Puede ser útil para recuperación, compatibilidad o tareas administrativas.

### 5. Otros endpoints de autenticación

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/send-verification-code`
- `POST /api/v1/auth/verify-code`

## Endpoints disponibles

### Salud del servicio

- `GET /api/v1/health`
- `GET /api/v1/health/accessibility`

### Usuarios

- `GET /api/v1/users/profile`
- `PUT /api/v1/users/profile`
- `DELETE /api/v1/users/account`
- `GET /api/v1/users/activity-log`

### Accesibilidad

- `GET /api/v1/accessibility/preferences/{user_id}`
- `PUT /api/v1/accessibility/preferences/{user_id}`
- `POST /api/v1/accessibility/detect-capabilities`
- `GET /api/v1/accessibility/voice-commands`
- `POST /api/v1/accessibility/log-usage`

## Formato de respuesta

La API busca mantener una salida consistente para clientes accesibles:

```json
{
  "success": true,
  "message": "Mensaje legible para usuarios y TTS",
  "message_type": "success",
  "data": {},
  "accessibility_info": {
    "announcement": "Texto sugerido para anunciar con lector de pantalla",
    "focus_element": "element-id",
    "haptic_pattern": "success"
  },
  "errors": [],
  "timestamp": "2026-03-23T12:00:00Z"
}
```

## Headers de accesibilidad

La aplicación añade headers como:

```http
X-Content-Accessible: true
X-Screen-Reader-Friendly: true
X-High-Contrast-Available: true
X-Voice-Commands-Supported: true
X-Extended-Timeout-Supported: true
```

## Testing

Tests incluidos en el repositorio:

```bash
pytest
pytest tests/test_accessibility.py -v
pytest tests/test_auth.py -v
```

> Importante: varios tests y el arranque de la aplicación dependen de configuración real de entorno y de una conexión MongoDB disponible.

## Despliegue en Vercel

Este repositorio ya trae lo necesario para desplegar en Vercel:

- `api/index.py` exporta la app ASGI.
- `vercel.json` enruta todas las requests hacia ese entrypoint.

Pasos generales:

1. Importa el repositorio en Vercel.
2. Configura el comando de instalación como `pip install -r requirements.txt`.
3. Carga todas las variables de entorno requeridas.
4. Despliega.

## Dependencias principales

Las dependencias actuales del proyecto son:

- `fastapi`
- `uvicorn[standard]`
- `motor`
- `pymongo`
- `passlib[bcrypt]`
- `bcrypt==4.0.1`
- `email-validator`
- `python-jose[cryptography]`
- `httpx`
- `pydantic-settings`
- `requests`

## Siguientes mejoras recomendadas

- Agregar un `.env.example` oficial.
- Documentar ejemplos de request/response por endpoint.
- Separar claramente los flujos legacy de autenticación de los flujos principales con código permanente.
- Incorporar una estrategia de testing desacoplada de MongoDB real para CI.
