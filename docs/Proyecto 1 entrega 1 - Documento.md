# Proyecto 1 – Entrega 1: Despliegue manual de un microservicio sobre AWS Elastic Beanstalk

**Curso:** DevOps: Agilizando el Despliegue Continuo de Aplicaciones – Universidad de los Andes
**Integrantes:** _<nombre 1>, <nombre 2>, <nombre 3>, <nombre 4>_
**Repositorio GitHub:** _<https://github.com/usuario/repositorio>_
**URL del ambiente:** http://blacklist-devops-e1.us-east-2.elasticbeanstalk.com
**Documentación Postman publicada:** _<https://documenter.getpostman.com/view/...>_
**Video de sustentación:** _<enlace>_

> Exporte este archivo a PDF con el nombre **"Proyecto 1 entrega 1 – Documento.pdf"**. Reemplace cada `[CAPTURA: ...]` con la imagen y cada `<...>` con el valor real.

---

## 0. Descripción de la solución

Microservicio REST en Python/Flask que gestiona la lista negra global de emails:

- `POST /blacklists`: agrega un email (`email`, `app_uuid` UUID obligatorio, `blocked_reason` opcional ≤ 255). Guarda la IP de origen y la fecha/hora de la solicitud.
- `GET /blacklists/<email>`: indica si el email está en la lista negra (`is_blacklisted`) y el motivo.
- `GET /health`: health check sin autenticación; devuelve la versión desplegada.

Autorización: Bearer Token estático (JWT firmado con `JWT_SECRET_KEY`, sin expiración). Persistencia: PostgreSQL en AWS RDS.

Stack: Flask, Flask-SQLAlchemy, Flask-RESTful, Flask-Marshmallow, Flask-JWT-Extended, Werkzeug, PostgreSQL, Gunicorn.

**Arquitectura:** Cliente (Postman) → Application Load Balancer → Auto Scaling Group (3–6 instancias EC2, Beanstalk Python) → RDS PostgreSQL (subred privada, SG que solo admite el SG de Beanstalk en el puerto 5432).

[CAPTURA: diagrama de arquitectura]

---

## 1. Creación y despliegue de la aplicación (10%)

### 1.a Configuración de RDS
- Motor: PostgreSQL 18.3 · Plantilla: Capa gratuita · Clase: db.t3.micro · Almacenamiento: 20 GB gp2 · Región: us-east-2 (Ohio)
- Identificador: blacklist-db · BD inicial: blacklist · Usuario: blacklist_admin · Acceso público: No · Single-AZ · Backups desactivados
- Security Group: blacklist-db-sg (sg-0c9569f7941dd1034) con regla de entrada 5432 únicamente desde blacklist-app-sg (sg-0c720c6080ec03df2), el SG asignado a las instancias de Beanstalk

[CAPTURA: creación de RDS – motor y plantilla]
[CAPTURA: configuración de conectividad / Security Group]
[CAPTURA: instancia RDS en estado "Disponible" con su endpoint]
[CAPTURA: regla de entrada del Security Group]

### 1.b Configuración del proyecto en AWS Elastic Beanstalk
- Aplicación: blacklist-app · Ambiente: blacklist-env · Plataforma: 64bit Amazon Linux 2023 v4.13.10 running Python 3.12 · Tipo: LoadBalanced (Application Load Balancer)
- Tipo de instancia: t3.micro · Auto Scaling: mín 3 / máx 6 · Subredes: us-east-2a, 2b, 2c
- Variables de entorno: `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD`, `JWT_SECRET_KEY`
- Código: paquete zip generado con `scripts/build_bundle.sh` (incluye `.ebextensions/01_environment.config` y `Procfile`)

[CAPTURA: creación de la aplicación y selección de plataforma]
[CAPTURA: carga del código fuente]
[CAPTURA: capacidad – Auto Scaling 3-6, balanceador]
[CAPTURA: propiedades del entorno (ocultar la contraseña)]
[CAPTURA: ambiente en estado "Ok" con la URL]
[CAPTURA: instancias EC2 en ejecución]

### 1.c Configuración de los health checks
- Ruta: `/health` (sin autenticación, responde `200 {"status":"ok","version":...}`)
- Intervalo 15 s · Timeout 5 s · Umbral saludable 3 · Umbral no saludable 5 · Código esperado 200
- Reporte de salud: mejorado (enhanced)

[CAPTURA: Configuración → Instancias y balanceador → proceso "default" con la ruta /health]
[CAPTURA: pestaña "Estado" con las instancias en "Ok"]
[CAPTURA: Target Group del ALB con los destinos "healthy"]

### 1.d Pruebas con Postman
Colección `postman/blacklist.postman_collection.json` (8 escenarios con tests automáticos): health check, agregar email (201), duplicado (409), datos inválidos (400), sin token (401), consulta de email bloqueado (true), consulta de email no bloqueado (false) y token inválido (401).

[CAPTURA: Runner de Postman con todos los tests en verde contra la URL de Beanstalk]
[CAPTURA: documentación publicada]
[CAPTURA: registro en la tabla blacklist con IP y fecha (opcional, vía consulta SQL)]

---

## 2. Estrategias de despliegue (20%)

**Metodología común para todas las estrategias**
1. Ambiente con Auto Scaling mín 3 / máx 6 (3 instancias en ejecución antes de cada despliegue).
2. Para cada despliegue se generó un nuevo zip con `scripts/build_bundle.sh` (v1.0.1, v1.0.2, ...); la versión queda en el archivo `VERSION` y la reporta `/health`.
3. **Validación de que el despliegue estaba en ejecución:** durante el despliegue se ejecutó `scripts/watch_deploy.sh`, que consulta `/health` cada segundo y registra el código HTTP y la versión que responde. Adicionalmente se observaron la pestaña **Eventos** de Beanstalk, la pestaña **Estado** (instancias y versión de cada una) y la consola de EC2 (IDs de instancia nuevas o existentes).
4. **Tiempo total:** desde el evento "Environment update is starting" hasta "Environment update completed successfully" en Eventos.

### Resumen

| Estrategia | Tamaño de lote | Instancias usadas (máx simultáneas) | Tiempo total | ¿Instancias iniciales o nuevas? | ¿Hubo caída? |
|---|---|---|---|---|---|
| All at once | – | _<3>_ | _<mm:ss>_ | _<iniciales>_ | _<sí, n s>_ |
| Rolling | _<1 instancia>_ | _<3>_ | _<mm:ss>_ | _<iniciales>_ | _<no>_ |
| Rolling with additional batch | _<1 instancia>_ | _<4>_ | _<mm:ss>_ | _<...>_ | _<no>_ |
| Immutable | – | _<6>_ | _<mm:ss>_ | _<nuevas>_ | _<no>_ |

### 2.1 All at once
- **Configuración:** Política de implementación = All at once.
- **a. Instancias utilizadas:** _<...>_
- **b. Validación:** _<describa lo observado en watch_deploy, Eventos, Estado>_
- **c. Tiempo total:** _<mm min ss s>_
- **d. Instancias iniciales o nuevas:** _<...>_ (comparar IDs de instancia antes/después)
- **e. Capturas:**
  [CAPTURA: configuración de la política]
  [CAPTURA: Eventos con inicio y fin del despliegue]
  [CAPTURA: Estado de las instancias durante el despliegue]
  [CAPTURA: extracto del log de watch_deploy]
- **f. Hallazgos:** _<...>_
  _Comportamiento esperado: despliega en todas las instancias al mismo tiempo; es el más rápido pero produce indisponibilidad mientras las instancias reinician la aplicación (códigos 502/503 en el log)._

### 2.2 Rolling
- **Configuración:** Rolling, tamaño de lote _<Fixed 1 / 33%>_.
- **a. Instancias utilizadas:** _<...>_
- **b. Validación:** _<...>_
- **c. Tiempo total:** _<...>_
- **d. Instancias iniciales o nuevas:** _<...>_
- **e. Capturas:** [CAPTURA: ...]
- **f. Hallazgos:** _<...>_
  _Comportamiento esperado: actualiza las instancias existentes por lotes, retirándolas del balanceador; no hay caída, pero la capacidad se reduce durante cada lote y conviven dos versiones (el log alterna entre la versión anterior y la nueva)._

### 2.3 Rolling with additional batch
- **Configuración:** Rolling with additional batch, tamaño de lote _<Fixed 1>_.
- **a. Instancias utilizadas:** _<...>_
- **b. Validación:** _<...>_
- **c. Tiempo total:** _<...>_
- **d. Instancias iniciales o nuevas:** _<...>_
- **e. Capturas:** [CAPTURA: ...]
- **f. Hallazgos:** _<...>_
  _Comportamiento esperado: primero lanza un lote adicional de instancias nuevas para mantener la capacidad completa y luego actualiza por lotes; al final termina el lote extra. Es más lento que Rolling y temporalmente usa más instancias (más costo)._

### 2.4 Immutable
- **Configuración:** Immutable.
- **a. Instancias utilizadas:** _<...>_
- **b. Validación:** _<...>_
- **c. Tiempo total:** _<...>_
- **d. Instancias iniciales o nuevas:** _<...>_
- **e. Capturas:** [CAPTURA: ...]
- **f. Hallazgos:** _<...>_
  _Comportamiento esperado: crea un Auto Scaling Group temporal con instancias nuevas con la nueva versión; cuando pasan los health checks las mueve al ASG original y termina las anteriores. Es el más lento, duplica temporalmente las instancias y permite un rollback limpio._

### 2.5 (Opcional) Traffic splitting
- **Configuración:** Traffic splitting, _<10%>_ de tráfico durante _<5>_ min.
- Hallazgos: _<...>_
  _Comportamiento esperado: canary; un porcentaje del tráfico va a instancias nuevas durante el tiempo de evaluación y si están sanas se mueve todo el tráfico._

### Conclusiones
_<Comparación de velocidad vs. disponibilidad vs. costo de cada estrategia y cuál recomiendan para este microservicio.>_
