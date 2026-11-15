# Infraestructura AWS: ambiente de contenedores en AWS Fargate (Entrega 3)

Responsable: Diego Rojas ([@diegorojasd](https://github.com/diegorojasd)) · Rama: `ft_fargate_manual` · Región: `us-east-2` (Ohio) · Cuenta: `002493919126`

Este documento registra el ambiente de contenedores del microservicio blacklist sobre AWS Fargate: la imagen, la Task Definition, el clúster, la red, el rol de IAM y el despliegue manual inicial del microservicio. El ambiente se configuró manualmente (sin plantilla de IaC ni pipeline) el 2026-11-14 y sobre él trabajan después CodeDeploy y el pipeline de CI/CD, documentados en [`pipeline-cicd.md`](pipeline-cicd.md).

## Resumen

| Recurso | Nombre | Estado verificado (2026-11-15) |
|---|---|---|
| Repositorio de imágenes (ECR) | `blacklist-app` | Privado, cifrado AES256, escaneo al subir activo |
| Task Definition | `blacklist-task` | Fargate, `awsvpc`, 0.25 vCPU / 512 MiB, Linux/X86_64 |
| Clúster ECS | `blacklist-cluster` | **Active**, solo capacidad Fargate, 1 servicio, 2 tareas en ejecución |
| Servicio ECS | `blacklist-service` | **Active**, 2/2 tareas, plataforma 1.4.0 |
| Red | VPC `vpc-0db07b6f5f2b5b97f` (por defecto), 3 subredes públicas | Tareas en `us-east-2b` y `us-east-2c` |
| Security Groups | `blacklist-ecs-alb-sg`, `blacklist-ecs-tasks-sg`, `blacklist-db-sg` | Encadenados: Internet → ALB → tareas → RDS |
| Balanceador | `blacklist-ecs-alb` (Application Load Balancer) | Activo, 2 destinos `healthy` |
| Rol de ejecución | `blacklist-ecs-task-execution-role` | Política administrada de ECS + política inline para los secretos |
| Secretos | `/blacklist/RDS_PASSWORD`, `/blacklist/JWT_SECRET_KEY` (SSM Parameter Store) | `SecureString` |
| Logs | `/ecs/blacklist` (CloudWatch Logs) | Retención de 7 días |

```
Internet ──▶ ALB blacklist-ecs-alb (:80 producción, :8080 pruebas)   SG blacklist-ecs-alb-sg
               └─▶ Tareas Fargate blacklist-app (:8000), 2 zonas      SG blacklist-ecs-tasks-sg
                     └─▶ RDS PostgreSQL blacklist-db (:5432)          SG blacklist-db-sg
```

## 1. Imagen del contenedor

El [`Dockerfile`](../Dockerfile) empaqueta la aplicación sobre `python:3.12-slim` (réplica de Docker Hub en Amazon ECR Public) y la sirve con Gunicorn en el puerto **8000**, con un usuario sin privilegios (`appuser`, uid 1000). El argumento `APP_VERSION` define la versión que reporta `GET /health`. [`.dockerignore`](../.dockerignore) deja fuera pruebas, documentación y archivos de Beanstalk.

Construcción y prueba local:

```bash
docker build --build-arg APP_VERSION=3.0.0 -t blacklist-app:3.0.0 .
docker run --rm -p 8000:8000 -e JWT_SECRET_KEY=<clave-de-32-caracteres-o-más> blacklist-app:3.0.0
curl http://localhost:8000/health      # {"status": "ok", "version": "3.0.0"}
```

Sin las variables `RDS_*` la aplicación usa SQLite, suficiente para comprobar que el contenedor arranca.

Publicación en ECR:

```bash
REGISTRY=002493919126.dkr.ecr.us-east-2.amazonaws.com
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin $REGISTRY
docker build --platform linux/amd64 --build-arg APP_VERSION=3.0.0 -t $REGISTRY/blacklist-app:3.0.0 .
docker push $REGISTRY/blacklist-app:3.0.0
```

`--platform linux/amd64` es necesario al construir desde un equipo ARM (Apple Silicon), porque la Task Definition exige `X86_64`.

## 2. Task Definition `blacklist-task`

La definición está versionada en [`taskdef.json`](../taskdef.json).

| Parámetro | Valor |
|---|---|
| Tipo de lanzamiento | `FARGATE` |
| Modo de red | `awsvpc` (cada tarea recibe su propia interfaz de red) |
| Tamaño | 256 unidades de CPU (0.25 vCPU) / 512 MiB |
| Plataforma | Linux / X86_64 |
| Rol de ejecución | `blacklist-ecs-task-execution-role` |
| Rol de tarea | Ninguno: la aplicación no llama a servicios de AWS |
| Contenedor | `blacklist-app`, puerto 8000/tcp, esencial |
| Variables de entorno | `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME` |
| Secretos | `RDS_PASSWORD` y `JWT_SECRET_KEY`, leídos de SSM Parameter Store al iniciar la tarea |
| Logs | Driver `awslogs` → grupo `/ecs/blacklist`, prefijo `blacklist` |

Las contraseñas no están en el repositorio ni en la Task Definition: solo se referencia el ARN del parámetro.

En `taskdef.json` la imagen es el marcador `<IMAGE1_NAME>`, que CodeDeploy reemplaza en cada despliegue. Para registrar una revisión a mano se sustituye por la URI de la imagen:

```bash
sed 's#<IMAGE1_NAME>#002493919126.dkr.ecr.us-east-2.amazonaws.com/blacklist-app:3.0.0#' taskdef.json > /tmp/taskdef.json
aws ecs register-task-definition --region us-east-2 --cli-input-json file:///tmp/taskdef.json
```

La revisión inicial es `blacklist-task:1` (imagen `blacklist-app:3.0.0`, registrada el 2026-11-14 por el usuario `devops-cli`). Las revisiones 2 a 8 las registró el pipeline de CI/CD.

## 3. Clúster y servicio

| Parámetro | Valor |
|---|---|
| Clúster | `blacklist-cluster`, proveedor de capacidad `FARGATE` (sin instancias EC2 registradas) |
| Servicio | `blacklist-service`, estrategia *Replica*, 2 tareas deseadas |
| Versión de plataforma | 1.4.0 |
| Subredes | `subnet-01e1367ae4e437185` (2a), `subnet-0c90619c6bb3a1e04` (2b), `subnet-06dc2b6f136e69cd4` (2c) |
| Security Group | `blacklist-ecs-tasks-sg` |
| IP pública | Habilitada (ver [sección 7](#8-supuestos-y-limitaciones)) |
| Balanceador | Contenedor `blacklist-app:8000` registrado en un grupo de destino del ALB |
| Controlador de despliegue | `CODE_DEPLOY` (blue/green) |

## 4. Red

Se usa la VPC por defecto de la cuenta, la misma de la base de datos RDS.

| Elemento | Valor |
|---|---|
| VPC | `vpc-0db07b6f5f2b5b97f` (`172.31.0.0/16`) |
| Subredes | Tres subredes públicas, una por zona (`us-east-2a`, `2b`, `2c`), con salida por Internet Gateway |
| Balanceador | `blacklist-ecs-alb`, *internet-facing*, en las tres subredes |
| Listeners | `:80` producción y `:8080` pruebas (lo usa CodeDeploy antes de mover el tráfico) |
| Grupos de destino | `blacklist-tg-blue` y `blacklist-tg-green`: tipo `ip`, puerto 8000, health check `GET /health` cada 15 s, código 200 |

Security Groups:

| Security Group | Entrada | Origen |
|---|---|---|
| `blacklist-ecs-alb-sg` (`sg-0a563e18fb6cc5cec`) | TCP 80 y 8080 | `0.0.0.0/0` |
| `blacklist-ecs-tasks-sg` (`sg-0ecb747fabbe0242f`) | TCP 8000 | Solo `blacklist-ecs-alb-sg` |
| `blacklist-db-sg` (`sg-075c2c7d98898c6a9`) | TCP 5432 | `blacklist-ecs-tasks-sg` y `blacklist-app-sg` (instancias de Beanstalk) |

Las tareas no son alcanzables desde Internet aunque tengan IP pública: su Security Group solo admite tráfico del balanceador. La base de datos sigue sin acceso público.

## 5. Rol `blacklist-ecs-task-execution-role`

- **Relación de confianza**: solo `ecs-tasks.amazonaws.com`.
- **`AmazonECSTaskExecutionRolePolicy`** (administrada por AWS): descargar la imagen de ECR y escribir en CloudWatch Logs.
- **`blacklist-ecs-secrets`** (inline): leer los secretos de la tarea.

| Servicio | Acciones | Recurso |
|---|---|---|
| SSM Parameter Store | `ssm:GetParameters` | `parameter/blacklist/*` |
| KMS | `kms:Decrypt` | Solo a través de SSM en `us-east-2` (`kms:ViaService`) |

El rol lo usa el agente de ECS para arrancar la tarea; el contenedor no recibe credenciales de AWS. ECS usa además su rol vinculado al servicio `AWSServiceRoleForECS`, que crea AWS.

## 6. Despliegue manual del microservicio

El primer despliegue se hizo a mano el 2026-11-14 con el usuario `devops-cli`, antes de que existiera el pipeline. La imagen contiene el microservicio completo: `GET /health`, `POST /blacklists` y `GET /blacklists/<email>`.

| Hora (UTC-5) | Paso | Resultado |
|---|---|---|
| 07:59:58 | `docker push` de `blacklist-app:3.0.0` a ECR | Imagen de 56,64 MB, digest `sha256:4ea11a36…` |
| 08:00:31 | Registro de la Task Definition | `blacklist-task:1` con la imagen `3.0.0` |
| 08:01:35 | Creación del servicio `blacklist-service` | 2 tareas deseadas, Fargate, detrás del ALB |
| 08:02:04 | Arranque de los contenedores | Gunicorn escuchando en `0.0.0.0:8000` con 3 workers |
| 08:02:14 | Primer health check del balanceador | `GET /health` → 200 en las dos tareas |
| 08:02:26 – 08:02:47 | Prueba funcional con `curl` y Postman por el balanceador | Respuestas esperadas (ver abajo) |

La imagen se construyó y publicó como en la [sección 1](#1-imagen-del-contenedor) y la Task Definition se registró como en la [sección 2](#2-task-definition-blacklist-task). El servicio se creó así:

```bash
aws ecs create-service --region us-east-2 --cluster blacklist-cluster --service-name blacklist-service \
  --task-definition blacklist-task:1 --desired-count 2 --launch-type FARGATE \
  --deployment-controller type=CODE_DEPLOY --health-check-grace-period-seconds 60 \
  --network-configuration 'awsvpcConfiguration={subnets=[subnet-01e1367ae4e437185,subnet-0c90619c6bb3a1e04,subnet-06dc2b6f136e69cd4],securityGroups=[sg-0ecb747fabbe0242f],assignPublicIp=ENABLED}' \
  --load-balancers targetGroupArn=<ARN de blacklist-tg-blue>,containerName=blacklist-app,containerPort=8000
```

### Inspección de los registros

Los logs de las dos tareas iniciales están en CloudWatch Logs, grupo `/ecs/blacklist`:

- **Arranque limpio.** Gunicorn 23.0.0 inicia, abre el puerto 8000 y levanta los 3 workers en menos de un segundo. No hay ningún evento `ERROR`, `CRITICAL` ni `Traceback` en los dos streams.
- **Conexión a RDS correcta.** `POST /blacklists` responde 201 y `GET /blacklists/<email>` responde 200, lo que confirma que la tarea leyó los secretos de SSM y escribió en la base de datos.
- **Health checks.** 79 respuestas 200 a `GET /health` por tarea, ninguna fallida.
- **Los 400, 401 y 409 son casos negativos de la colección de Postman** (cuerpo inválido, sin token, email duplicado), no errores de la aplicación.
- **Cierre.** Las tareas terminaron a las 08:17:59 con `Handling signal: term`: las reemplazó el primer despliegue del pipeline (versión `3.0.1`), no una falla.

Como el grupo de logs retiene 7 días, los primeros eventos de cada tarea quedaron exportados en [`evidencias/fg-logs-inicio.txt`](evidencias/fg-logs-inicio.txt).

```bash
# Streams del grupo, del más antiguo al más reciente
aws logs describe-log-streams --region us-east-2 --log-group-name /ecs/blacklist --order-by LastEventTime --no-descending

# Eventos de una tarea desde el arranque
aws logs get-log-events --region us-east-2 --log-group-name /ecs/blacklist \
  --log-stream-name blacklist/blacklist-app/<id-de-la-tarea> --start-from-head

# Búsqueda de errores en todo el grupo
aws logs filter-log-events --region us-east-2 --log-group-name /ecs/blacklist --filter-pattern '?ERROR ?Traceback ?CRITICAL'
```

Los despliegues posteriores ya no son manuales: los hace CodeDeploy desde el pipeline.

## 7. Verificación

Estado del 2026-11-15:

- Clúster `blacklist-cluster`: **Active**, 1 servicio activo, 2 tareas *Running*, 0 pendientes.
- Tareas: `blacklist-task:8` en `us-east-2b` y `us-east-2c`, Fargate 1.4.0.
- Grupo de destino en uso: 2 destinos `healthy`.
- `GET /health` por el balanceador: HTTP 200, `{"status": "ok", "version": "3.0.9"}`.

Comandos (solo lectura):

```bash
# Clúster y servicio
aws ecs describe-clusters --region us-east-2 --clusters blacklist-cluster \
  --query 'clusters[0].[status,activeServicesCount,runningTasksCount,capacityProviders]'
aws ecs describe-services --region us-east-2 --cluster blacklist-cluster --services blacklist-service \
  --query 'services[0].{Estado:status,Deseadas:desiredCount,Activas:runningCount,TaskDef:taskDefinition,Red:networkConfiguration}'

# Task Definition
aws ecs describe-task-definition --region us-east-2 --task-definition blacklist-task \
  --query 'taskDefinition.{Rev:revision,CPU:cpu,Mem:memory,Rol:executionRoleArn,Imagen:containerDefinitions[0].image}'

# Security Groups
aws ec2 describe-security-groups --region us-east-2 \
  --group-ids sg-0a563e18fb6cc5cec sg-0ecb747fabbe0242f sg-075c2c7d98898c6a9

# Rol
aws iam list-attached-role-policies --role-name blacklist-ecs-task-execution-role
aws iam get-role-policy --role-name blacklist-ecs-task-execution-role --policy-name blacklist-ecs-secrets

# Aplicación
curl http://blacklist-ecs-alb-493993814.us-east-2.elb.amazonaws.com/health
```

## 8. Supuestos y limitaciones

- **Tareas en subredes públicas con IP pública.** La VPC por defecto no tiene subredes privadas ni NAT Gateway, y sin salida a Internet la tarea no puede descargar la imagen de ECR ni leer los secretos. Se asigna IP pública para no pagar un NAT Gateway; el acceso de entrada lo restringe el Security Group.
- **Sin rol de tarea.** Si la aplicación llegara a usar servicios de AWS, habría que crear uno y agregarlo como `taskRoleArn`.
- **Sin escalado automático.** El servicio mantiene 2 tareas fijas.
- **Las capturas muestran el estado actual, no el del día de la creación.** Para la fecha de las capturas el pipeline ya había desplegado varias versiones; por eso el servicio corre `blacklist-task:8`. La Task Definition inicial se evidencia con la revisión 1.
- **Costo.** Fargate, el balanceador y RDS se cobran mientras estén activos. Hay que eliminarlos al cerrar la entrega.
- La infraestructura se creó manualmente; no hay plantilla de IaC en el repositorio.

## 9. Evidencia para el documento de la entrega

Las capturas están en [`evidencias/`](evidencias/):

| Archivo | Contenido |
|---|---|
| `fg-cluster.png` | `blacklist-cluster`: Active, 1 servicio activo, 2 tareas en ejecución; `blacklist-service` con 2/2 tareas |
| `fg-tareas.png` | Pestaña Tasks: dos tareas *Running* en Fargate 1.4.0, zonas `us-east-2b` y `us-east-2c` |
| `fg-task-definition.png` | `blacklist-task:1`: Fargate, `awsvpc`, Linux/X86_64, rol de ejecución, 0.25 vCPU / 512 MiB |
| `fg-servicio-red.png` | `blacklist-service` → Configuration and networking: VPC, subredes y Security Group |
| `fg-sg-tareas.png` | `blacklist-ecs-tasks-sg`: entrada TCP 8000 solo desde el Security Group del balanceador |
| `fg-sg-alb.png` | `blacklist-ecs-alb-sg`: entrada TCP 80 y 8080 |
| `fg-ecr-imagen.png` | Repositorio `blacklist-app` en ECR: imagen `3.0.0` del despliegue manual y las que publicó el pipeline |
| `fg-logs-inicio.png` | CloudWatch Logs, tarea inicial: arranque de Gunicorn, health checks 200 y primeras peticiones |
| `fg-logs-inicio.txt` | Primeros 25 eventos de log de cada una de las dos tareas iniciales |
| `fg-tarea-running.png` | Detalle de una tarea del servicio: *Last status* Running, Fargate, 0.25 vCPU / 0.5 GiB |
| `fg-servicio-salud.png` | `blacklist-service`: Active, 2 tareas en ejecución, despliegue *Succeeded* |
| `fg-iam-rol.png` | `blacklist-ecs-task-execution-role`: `AmazonECSTaskExecutionRolePolicy` y la política inline `blacklist-ecs-secrets` |

Capturas tomadas el 2026-11-15.
