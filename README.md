# COMPAS API (Backend)

> Backend REST del sistema COMPAS. Gestiona autenticación de usuarios, persistencia de sesión y preferencias de accesibilidad para la aplicación móvil COMPAS.

**Repositorio:** https://github.com/JuanSO121/compas-api  
**Autores:** Juan José Sánchez Ocampo · Carlos Eduardo Rangel  
**Institución:** Universidad de San Buenaventura Cali — Ingeniería de Sistemas e Ingeniería Multimedia, 2026

---

## Tabla de contenido

- [Resumen ejecutivo](#resumen-ejecutivo)
- [Arquitectura](#arquitectura)
- [Tecnologías](#tecnologías)
- [Endpoints](#endpoints)
- [Modelo de datos](#modelo-de-datos)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Despliegue](#despliegue)
- [Seguridad](#seguridad)
- [Repositorios relacionados](#repositorios-relacionados)

---

## Resumen ejecutivo

COMPAS API es el backend del sistema COMPAS. Desarrollado con FastAPI y desplegado en Vercel, expone endpoints REST para autenticación mediante JWT, gestión de sesión de usuario y consulta de preferencias de accesibilidad. La base de datos es MongoDB Atlas con conexión asíncrona mediante Motor.

El backend es requerido únicamente para autenticación y carga de preferencias. La navegación, segmentación semántica y guía de voz operan de forma completamente local en el dispositivo, sin depender del backend durante el uso activo.

### Funcionalidades implementadas

- Registro de usuario con correo, contraseña y nombre.
- Envío automático de código de acceso permanente de seis dígitos al correo del usuario (SMTP/Gmail).
- Autenticación por código de acceso con emisión de tokens JWT (access token + refresh token).
- Refresco automático de sesión y bloqueo temporal tras cinco intentos fallidos consecutivos.
- Consulta y actualización de preferencias de accesibilidad del usuario.
- Almacenamiento de credenciales con hash seguro (bcrypt).

---

## Arquitectura

```
Aplicación Flutter
      ↓ HTTPS / JWT
Servidor Vercel (FastAPI)
  ├── /auth     → registro, login, refresh, bloqueo
  └── /users    → perfil y preferencias de usuario
      ↓ async (Motor)
MongoDB Atlas
  └── Colección "users"
      ↓
Servidor SMTP (Gmail)
  └── Envío de código de acceso al correo del usuario
```

---

## Tecnologías

| Tecnología | Uso |
|-----------|-----|
| FastAPI | Framework REST asíncrono |
| Motor | Driver async oficial de MongoDB para Python |
| MongoDB Atlas | Base de datos en la nube |
| JWT (PyJWT) | Autenticación stateless |
| bcrypt | Hash seguro de contraseñas |
| SMTP / Gmail | Envío de código de acceso por correo |
| Vercel | Plataforma de despliegue serverless |
| Python 3.11+ | Lenguaje de implementación |

---

## Endpoints

### Autenticación (`/auth`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/register` | Registro de nuevo usuario |
| POST | `/auth/login` | Login por código de acceso de seis dígitos |
| POST | `/auth/refresh` | Refresco de access token |
| POST | `/auth/request-code` | Solicita nuevo código de acceso |

### Usuarios (`/users`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/users/me` | Obtiene perfil y preferencias del usuario |
| PUT | `/users/preferences` | Actualiza preferencias de accesibilidad |

---

## Modelo de datos

### Colección `users`

```json
{
  "_id": "ObjectId",
  "email": "string",
  "password_hash": "string",
  "name": "string",
  "access_code": "string (6 dígitos, hash)",
  "failed_attempts": "int",
  "locked_until": "datetime | null",
  "preferences": {
    "voice_speed": "float",
    "language": "string"
  },
  "created_at": "datetime"
}
```

---

## Instalación y ejecución

```bash
# Clonar repositorio
git clone https://github.com/JuanSO121/compas-api.git
cd compas-api

# Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con las credenciales de MongoDB y SMTP

# Ejecutar en desarrollo
uvicorn main:app --reload
```

### Variables de entorno requeridas

```env
MONGODB_URI=mongodb+srv://...
JWT_SECRET=tu_clave_secreta
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=tu_app_password
```

---

## Despliegue

El backend está configurado para despliegue en Vercel mediante `vercel.json`. Cada push a la rama principal activa un despliegue automático.

```bash
# Desplegar con Vercel CLI
vercel --prod
```

---

## Seguridad

- Las contraseñas se almacenan con hash bcrypt, nunca en texto plano.
- Los tokens JWT tienen tiempo de expiración configurable.
- El código de acceso se almacena hasheado; solo el usuario recibe el valor original por correo.
- Las cuentas se bloquean temporalmente tras cinco intentos fallidos consecutivos de autenticación.
- Toda la comunicación se realiza sobre HTTPS.

---

## Repositorios relacionados

| Módulo | Repositorio |
|--------|------------|
| Aplicación móvil (Flutter) | https://github.com/JuanSO121/compas-client-mobile |
| Módulo AR (Unity) | https://github.com/JuanSO121/Compas_AR |
