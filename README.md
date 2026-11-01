# Blacklist Microservice – Entrega 1 DevOps

Microservicio REST para gestionar la **lista negra global de emails** de la organización. Construido con Python + Flask y desplegado manualmente (sin CI/CD) en **AWS Elastic Beanstalk** con **PostgreSQL en AWS RDS**.

Universidad de los Andes · DevOps: Agilizando el Despliegue Continuo de Aplicaciones · Proyecto – Entrega 1

## Integrantes

| Integrante | GitHub | Responsabilidad |
|---|---|---|
| David Rojas | [@DRJ244](https://github.com/DRJ244) | Endpoint `POST /blacklists` (`ft_post_blacklist`) |
| Ruben Camargo | [@RubenCamargo23](https://github.com/RubenCamargo23) | Endpoint `GET /blacklists/<email>` y Postman (`ft_get_blacklist`) |
| Diego Rojas | [@diegorojasd](https://github.com/diegorojasd) | Infraestructura AWS: RDS y Elastic Beanstalk (`ft_infra_aws`) |
| Brian Martínez | [@martzb](https://github.com/martzb) | Estrategias de despliegue (`ft_estrategias_despliegue`) |

| Recurso | Enlace |
|---|---|
| Ambiente en AWS | http://blacklist-devops-e1.us-east-2.elasticbeanstalk.com |
| Documentación de la API (Postman) | https://documenter.getpostman.com/view/59040697/2sBYHSxfzC |
| Backlog (tablero Kanban) | https://github.com/users/RubenCamargo23/projects/2 |

## Arquitectura

![Arquitectura](docs/arquitectura.png)

Cliente (Postman) → Application Load Balancer → Auto Scaling Group (3–6 instancias EC2 t3.micro, Python 3.12 en Amazon Linux 2023) → RDS PostgreSQL (sin acceso público; su Security Group solo admite el puerto 5432 desde el Security Group de las instancias).

## Stack

| Componente | Uso |
|---|---|
| Flask 3 / Werkzeug | Framework web / WSGI |
| Flask-SQLAlchemy | ORM (modelo `Blacklist`) |
| Flask-RESTful | Recursos REST |
| Flask-Marshmallow | Validación y serialización |
| Flask-JWT-Extended | Autorización con Bearer Token (JWT estático, sin expiración) |
| PostgreSQL (AWS RDS) | Persistencia |
| Gunicorn | Servidor WSGI en Beanstalk |

## Estructura

```
application.py              # Punto de entrada WSGI (objeto "application" que usa Beanstalk)
app/
  __init__.py               # create_app(): extensiones, rutas, errores JWT, versión
  config.py                 # Conexión a BD (DATABASE_URL o RDS_*), JWT
  models.py                 # Modelo Blacklist
  schemas.py                # Validación Marshmallow
  resources.py              # Endpoints (Flask-RESTful)
.ebextensions/              # Beanstalk: ALB, Auto Scaling 3-6, health check /health
Procfile                    # gunicorn
postman/                    # Colección y environments exportados (JSON)
scripts/
  generate_token.py         # Genera el Bearer token estático
  build_bundle.sh           # Empaqueta el .zip para subir a Beanstalk
  watch_deploy.sh           # Monitorea /health durante un despliegue
tests/                      # Pruebas unitarias (pytest)
docs/                       # Diagrama de arquitectura y documento de la entrega
```

## API

Todos los endpoints `/blacklists` requieren `Authorization: Bearer <token>`.

### `POST /blacklists`

```json
{
  "email": "cliente@example.com",
  "app_uuid": "3f0f0b4e-6b1a-4c9e-9a51-2f1d7c8a9b10",
  "blocked_reason": "Envío masivo de spam"
}
```

| Campo | Tipo | Reglas |
|---|---|---|
| `email` | String | Obligatorio, email válido. Se guarda en minúsculas y es único |
| `app_uuid` | String | Obligatorio, UUID válido |
| `blocked_reason` | String | Opcional, máximo 255 caracteres |

Guarda además la **IP de origen** (primer valor de `X-Forwarded-For`, porque en Beanstalk la petición llega a través del balanceador) y la **fecha/hora** de la solicitud.

| Código | Significado |
|---|---|
| 201 | Email agregado |
| 400 | Datos inválidos (detalle en `errors`) |
| 401 | Token ausente o inválido |
| 409 | El email ya está en la lista negra |

### `GET /blacklists/<email>`

```json
{ "email": "cliente@example.com", "is_blacklisted": true, "blocked_reason": "Envío masivo de spam" }
```

### `GET /health`

Sin autenticación. Lo usa el balanceador como health check y devuelve la versión desplegada (archivo `VERSION` que genera `build_bundle.sh`):

```json
{ "status": "ok", "version": "1.0.4" }
```

## Ejecución local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python application.py           # http://localhost:8000 (usa SQLite si no hay DATABASE_URL)

# Con PostgreSQL:
DATABASE_URL=postgresql://usuario:clave@localhost:5432/blacklist python application.py
```

> En macOS el puerto 5000 lo ocupa AirPlay; por eso se usa el 8000.

Token para probar los endpoints protegidos (debe firmarse con la misma `JWT_SECRET_KEY` que usa la app):

```bash
JWT_SECRET_KEY=<clave> python scripts/generate_token.py
```

## Pruebas

Las pruebas unitarias están en `tests/` y se ejecutan con `pytest` usando una base de datos SQLite en memoria (`TestConfig`).

Para ejecutar las pruebas generando el reporte JUnit (`reports/junit.xml`, utilizado por AWS CodeBuild) y el reporte de cobertura con `pytest-cov` (`reports/coverage.xml` y porcentaje en consola):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest --junitxml=reports/junit.xml --cov=app --cov-report=xml:reports/coverage.xml --cov-report=term
```

| Archivo generado | Formato | Propósito |
|---|---|---|
| `reports/junit.xml` | JUnit XML | Reporte de resultados de pruebas unitarias para AWS CodeBuild |
| `reports/coverage.xml` | Cobertura XML | Reporte de cobertura de código (≈96%) para AWS CodeBuild |

## Pruebas con Postman

- **Documentación publicada:** https://documenter.getpostman.com/view/59040697/2sBYHSxfzC (botón *Run in Postman*).
- **Colección:** `postman/blacklist.postman_collection.json`, con 8 escenarios y tests automáticos: health, agregar (201), duplicado (409), datos inválidos (400), sin token (401), consultar email bloqueado y no bloqueado, token inválido (401).
- La colección ya trae `base_url`, `token` y `app_uuid` como variables de colección, así que **se ejecuta contra AWS sin seleccionar environment**: *Import* → clic derecho en la colección → *Run collection*.
- Environments opcionales en `postman/`: `blacklist-aws-SIN-TOKEN` (si Postman bloquea la importación por *Secrets Detected*), `blacklist-aws` y `blacklist-local`.

Desde la terminal:

```bash
npx newman run postman/blacklist.postman_collection.json
```

## Despliegue manual en AWS

### 1. RDS (PostgreSQL)
- PostgreSQL, plantilla capa gratuita, `db.t3.micro`, 20 GB, sin acceso público, base de datos inicial `blacklist`.
- Security Group `blacklist-db-sg`: entrada **5432** solo desde el Security Group de las instancias de Beanstalk.
- La tabla `blacklist` la crea la aplicación al arrancar.

### 2. Elastic Beanstalk
1. Generar el paquete: `bash scripts/build_bundle.sh 1.0.0` → `dist/blacklist-1.0.0.zip`.
2. Crear la aplicación y el ambiente: plataforma **Python 3.12 (Amazon Linux 2023)**, alta disponibilidad, `t3.micro`. `.ebextensions` fija el ALB, Auto Scaling **mín 3 / máx 6** y el health check en `/health`.
3. Propiedades del entorno:

| Variable | Descripción |
|---|---|
| `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD` | Conexión a RDS |
| `JWT_SECRET_KEY` | Clave para firmar el token (32 caracteres o más) |

4. Verificar: `curl http://<ambiente>.elasticbeanstalk.com/health`.

### 3. Estrategias de despliegue
Para cada estrategia: cambiar la política en *Configuration → Updates, monitoring, and logging*, generar una nueva versión con `build_bundle.sh <versión>`, ejecutar el monitor y desplegar con *Upload and deploy*:

```bash
bash scripts/watch_deploy.sh http://blacklist-devops-e1.us-east-2.elasticbeanstalk.com mediciones/deploy-<estrategia>.log
```

Resultados medidos (3 instancias, lote fijo de 1 en las estrategias por lotes):

| Estrategia | Instancias (máx) | Tiempo total | ¿Iniciales o nuevas? | ¿Caída? |
|---|---|---|---|---|
| All at once | 3 | 1 min 01 s | Iniciales | Sí (≈4 s, HTTP 502) |
| Rolling | 3 (2 en servicio por lote) | 9 min 17 s | Iniciales | No |
| Rolling with additional batch | 4 (3 + 1) | 9 min 20 s | Mixtas (1 nueva + 2 iniciales) | No |
| Immutable | 6 (3 + 3) | 18 min 59 s | Todas nuevas | No |

### 4. Limpieza
Al terminar, eliminar los recursos para no generar costos: en GitHub, *Actions → 🧨 Eliminar infraestructura AWS → Run workflow* (escribiendo `ELIMINAR`), o manualmente terminando el ambiente de Beanstalk, la instancia RDS y los Security Groups.

## Ramas y flujo de trabajo

| Rama | Propósito |
|---|---|
| `main` | Versión entregada. Solo recibe merges desde `develop` |
| `develop` | Integración del equipo |
| `ft_post_blacklist` | Integrante 1 – Endpoint `POST /blacklists` |
| `ft_get_blacklist` | Integrante 2 – Endpoint `GET /blacklists/<email>` + Postman |
| `ft_infra_aws` | Integrante 3 – RDS + Elastic Beanstalk + health checks |
| `ft_estrategias_despliegue` | Integrante 4 – Estrategias de despliegue |

Cada integrante trabaja en su rama `ft_*` y abre un Pull Request hacia `develop`. Cuando todo está integrado y probado en AWS, se hace el PR `develop → main`. Las tareas están en la pestaña **Issues** (milestone *Entrega 1*) y en el tablero Kanban.
