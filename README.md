# Backend Accesible - API FastAPI para Personas Ciegas y con Baja Visión

## 🎯 Objetivo

Backend completo y gratuito diseñado específicamente para aplicaciones accesibles, optimizado para tecnologías asistivas como lectores de pantalla y síntesis de voz.

## ✨ Características Principales

### 🔧 Stack Tecnológico (100% Gratuito)
- **FastAPI**: Framework web moderno y rápido
- **MongoDB Atlas**: Base de datos en la nube (tier gratuito)
- **Gmail SMTP**: Servicio de email gratuito
- **JWT**: Autenticación sin dependencias externas
- **BCrypt**: Encriptación segura de contraseñas
- **Python 3.8+**: Lenguaje base

### ♿ Características de Accesibilidad
- **Respuestas estructuradas** para TTS (Text-to-Speech)
- **Headers HTTP específicos** para tecnologías asistivas
- **Rate limiting inclusivo** (más permisivo para usuarios de accesibilidad)
- **Mensajes de error descriptivos** optimizados para lectores de pantalla
- **Validaciones con sugerencias** claras y útiles
- **Timeouts extendidos** para usuarios que necesitan más tiempo
- **Logging especializado** para eventos de accesibilidad

### 🔐 Seguridad Robusta
- Autenticación JWT con refresh tokens
- Validación exhaustiva con mensajes accesibles
- Rate limiting inteligente por IP y usuario
- Bloqueo temporal de cuentas por intentos fallidos
- Verificación de email obligatoria
- Reseteo seguro de contraseñas

## 🚀 Instalación y Configuración

### 1. Clonar y Configurar Entorno
```bash
# Clonar el repositorio (cuando esté disponible)
git clone <repo-url>
cd accessible-backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus configuraciones
nano .env
```

**Configuraciones requeridas en .env:**

```env
# MongoDB Atlas (crear cuenta gratuita en mongodb.com)
DATABASE_URL=mongodb+srv://usuario:password@cluster0.mongodb.net/accessible_app

# Gmail SMTP (activar "App Passwords" en tu cuenta Google)
SMTP_USERNAME=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password_generado
FROM_EMAIL=tu_email@gmail.com

# JWT (generar clave segura)
JWT_SECRET_KEY=tu-clave-super-secreta-aqui

# Frontend URL (para emails de verificación)
FRONTEND_URL=http://localhost:3000
```

### 3. Configurar MongoDB Atlas (Gratuito)

1. **Crear cuenta en [MongoDB Atlas](https://www.mongodb.com/atlas/database)**
2. **Crear cluster gratuito** (M0 Sandbox - 512MB)
3. **Configurar acceso:**
   - IP Address: `0.0.0.0/0` (para desarrollo)
   - Usuario de base de datos con permisos de lectura/escritura
4. **Obtener string de conexión** y agregarlo a `.env`

### 4. Configurar Gmail SMTP (Gratuito)

1. **Activar verificación en 2 pasos** en tu cuenta Google
2. **Generar contraseña de aplicación:**
   - Google Account → Security → App passwords
   - Seleccionar "Mail" y "Other"
   - Copiar contraseña generada a `SMTP_PASSWORD`

### 5. Ejecutar la Aplicación

```bash
# Desarrollo con recarga automática
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# O usar el comando directo
python -m app.main
```

## 📚 Uso de la API

### Endpoints Principales

#### Autenticación
```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
```

#### Gestión de Usuarios
```http
GET /api/v1/users/profile
PUT /api/v1/users/profile
DELETE /api/v1/users/account
GET /api/v1/users/activity-log
```

#### Accesibilidad
```http
GET /api/v1/accessibility/preferences/{user_id}
PUT /api/v1/accessibility/preferences/{user_id}
POST /api/v1/accessibility/detect-capabilities
GET /api/v1/accessibility/voice-commands
POST /api/v1/accessibility/log-usage
```

#### Health Checks
```http
GET /api/v1/health
GET /api/v1/health/accessibility
```

### Ejemplo de Respuesta Accesible

Todas las respuestas siguen este formato para máxima compatibilidad:

```json
{
  "success": true,
  "message": "Mensaje descriptivo para TTS",
  "message_type": "success",
  "data": {
    // Datos de respuesta
  },
  "accessibility_info": {
    "announcement": "Mensaje para anunciar via TTS",
    "focus_element": "elemento-a-enfocar",
    "haptic_pattern": "success"
  },
  "errors": [],
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### Headers de Accesibilidad

Cada respuesta incluye headers específicos:

```http
X-Content-Accessible: true
X-Screen-Reader-Friendly: true
X-High-Contrast-Available: true
X-Voice-Commands-Supported: true
X-Process-Time: 0.0234
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Tests con coverage
pytest --cov=app

# Tests específicos de accesibilidad
pytest tests/test_accessibility.py -v

# Tests de autenticación
pytest tests/test_auth.py -v
```

## 🚀 Deployment Gratuito

### Opciones Recomendadas:

#### 0. **Vercel (recomendado para FastAPI serverless)**

Este repositorio ya incluye configuración para Vercel (`vercel.json` + `api/index.py`).

1. En Vercel: **New Project → Import Git Repository**
2. Selecciona `JuanSO121/compas-api` y rama `main`
3. Usa estos valores:
   - **Framework Preset**: `FastAPI`
   - **Root Directory**: `./`
   - **Build Command**: `None`
   - **Output Directory**: `N/A`
   - **Install Command**: `pip install -r requirements.txt`
4. En **Environment Variables**, carga todas las variables requeridas por `app/config/settings.py`:
   - `DATABASE_URL`
   - `DATABASE_NAME`
   - `JWT_SECRET_KEY`
   - `JWT_ALGORITHM`
   - `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
   - `JWT_REFRESH_TOKEN_EXPIRE_DAYS`
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `FROM_EMAIL`
   - `FROM_NAME`
   - `ALLOWED_ORIGINS` (formato JSON, por ejemplo: `["https://tu-frontend.vercel.app"]`)
   - `BCRYPT_ROUNDS`
   - `MAX_LOGIN_ATTEMPTS`
   - `LOCKOUT_DURATION_MINUTES`
   - `REDIS_URL`
   - `USE_REDIS` (`true` o `false`)
   - `FRONTEND_URL`
5. Haz clic en **Deploy**.

> Nota: en Vercel no necesitas ejecutar `uvicorn` manualmente; Vercel levanta la app ASGI desde `api/index.py`.

1. **Render.com** (750 horas gratuitas/mes)
```bash
# Conectar repositorio GitHub a Render
# Configurar variables de entorno
# Deploy automático
```

2. **Railway** ($5 de crédito inicial)
```bash
railway login
railway init
railway add
railway deploy
```

3. **Heroku** (tier básico gratuito)
```bash
heroku create tu-app-accesible
heroku config:set DATABASE_URL=tu_mongodb_url
git push heroku main
```

### Variables de Entorno para Producción:
```bash
# Todas las mismas de .env más:
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
```

## 📋 Monitoreo y Logs

### Logs de Accesibilidad
El sistema registra automáticamente:
- Eventos de uso de características accesibles
- Errores específicos de navegación
- Cambios en preferencias de accesibilidad
- Performance de endpoints críticos

### Métricas Importantes
- Tiempo de respuesta (optimizado para tecnologías asistivas)
- Rate limiting por tipo de usuario
- Errores de validación más comunes
- Uso de comandos de voz

## 🤝 Contribución

### Principios de Desarrollo Accesible:
1. **Mensajes claros**: Siempre usar lenguaje descriptivo
2. **Respuestas consistentes**: Mantener formato estructurado
3. **Performance optimizado**: Considerar conexiones lentas
4. **Inclusividad**: Rate limiting más permisivo para usuarios de accesibilidad
5. **Testing exhaustivo**: Incluir tests de accesibilidad

### Estructura para Nuevas Características:
```python
# Siempre usar el helper para respuestas
return AccessibleHelpers.create_accessible_response(
    success=True,
    message="Mensaje descriptivo para TTS",
    data=your_data,
    accessibility_info={
        "announcement": "Mensaje para anunciar",
        "focus_element": "elemento-destino",
        "haptic_pattern": "success|error|warning|info"
    }
)
```

## 📞 Soporte

- **Email**: soporte@tu-app.com
- **Documentación**: `/api/v1/docs` (Swagger UI accesible)
- **Status**: `/api/v1/health/accessibility`

## 📄 Licencia

MIT License - Libre para uso comercial y personal.

## 🎉 Próximos Pasos

Este backend está listo para integrarse con:
1. **Flutter Android** (paso 2 del proyecto)
2. **Aplicaciones web accesibles**
3. **Servicios de síntesis de voz**
4. **Sistemas de comandos por voz**

¡El backend está completo y listo para producción con todas las características de accesibilidad implementadas!
