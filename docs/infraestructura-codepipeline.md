# Infraestructura AWS: pipeline de integración continua con CodePipeline (Entrega 2)

Responsable: Diego Rojas ([@diegorojasd](https://github.com/diegorojasd)) · Rama: `ft_infra_ci` · Región: `us-east-2` (Ohio)

Este documento registra el pipeline que ejecuta automáticamente la integración continua cuando hay un commit en la rama principal: la conexión con GitHub, las etapas del pipeline y cómo verificarlo. El build que corre el pipeline es el proyecto CodeBuild `blacklist-ci`, documentado en [`infraestructura-codebuild.md`](infraestructura-codebuild.md).

> **Rama principal: `main`, no `master`.** El enunciado habla de la rama `master`. En este repositorio la rama principal se llama `main` (el nombre por defecto de GitHub). Cumple el mismo papel: es la rama de la versión entregada y solo recibe merges desde `develop`.

## Resumen

| Recurso | Nombre | Estado |
|---|---|---|
| Conexión con GitHub | `blacklist-github` (AWS CodeConnections) | **Available** |
| Repositorio | `RubenCamargo23/entregaUnoDevOps` | Autorizado por el dueño del repositorio |
| Pipeline | `blacklist-ci-pipeline` (tipo V2, modo QUEUED) | Source → Build, sin Deploy |
| Rama que dispara el pipeline | `main`, por push | ⏳ Pendiente: hoy apunta a `apoyo_entrega2` (ver [sección 4](#4-cambio-de-rama-a-main)) |
| Rol del pipeline | `blacklist-codepipeline-role` | Permisos mínimos |
| Almacén de artefactos | `blacklist-ci-artifacts-002493919126` | El mismo bucket del CI |

```
push a main ──► Source (GitHub vía blacklist-github) ──► Build (CodeBuild blacklist-ci) ──► artefacto en S3
                                                          pruebas + reportes; sin Deploy
```

## 1. Conexión con GitHub

- **Nombre**: `blacklist-github`.
- **Proveedor**: GitHub, mediante la app *AWS Connector for GitHub*.
- **Estado**: `Available`.
- **ARN**: `arn:aws:codeconnections:us-east-2:002493919126:connection/e04df9f9-0bd8-409d-bd8a-ec33156b4312`.

Una conexión nueva queda en `Pending` hasta que el dueño del repositorio (Ruben Camargo, `RubenCamargo23`) la autoriza en GitHub instalando la app. El estado `Available` confirma que esa autorización existe.

## 2. Pipeline `blacklist-ci-pipeline`

| Etapa | Acción | Proveedor | Configuración |
|---|---|---|---|
| **Source** | `GitHub` | CodeStarSourceConnection | Repositorio `RubenCamargo23/entregaUnoDevOps`, rama `main`, `DetectChanges = true`, salida `CODE_ZIP` → `SourceOutput` |
| **Build** | `PruebasYArtefacto` | CodeBuild | Proyecto `blacklist-ci`, entrada `SourceOutput` → `BuildArtifact` |

- **Disparador**: trigger de tipo push sobre la acción `GitHub`, filtrado a la rama `main`. Un push o un merge de PR a `main` inicia una ejecución; los pushes a otras ramas no la inician.
- **Sin etapa Deploy**: la entrega es solo CI. El artefacto queda en S3 y el despliegue a Elastic Beanstalk se hace aparte.
- **Si las pruebas fallan, la ejecución falla.** El `post_build` del `buildspec.yml` no genera el artefacto y la etapa Build queda en `Failed`.

### Rol `blacklist-codepipeline-role`

Usa una política inline, `blacklist-codepipeline-policy`:

| Servicio | Acciones | Recurso |
|---|---|---|
| S3 | `GetObject`, `GetObjectVersion`, `PutObject`, `GetBucketVersioning`, `GetBucketLocation` | Solo `blacklist-ci-artifacts-002493919126` |
| CodeBuild | `StartBuild`, `BatchGetBuilds` | Solo el proyecto `blacklist-ci` |
| CodeConnections | `UseConnection` | Solo la conexión `blacklist-github` |

No tiene permisos de despliegue (Elastic Beanstalk, CodeDeploy), coherente con que el pipeline no tiene etapa Deploy.

## 3. Historial previo (rama de apoyo)

El pipeline se creó y se probó contra la rama `apoyo_entrega2`, porque `main` todavía no tenía `buildspec.yml`:

| Ejecución | Disparo | Commit | Resultado |
|---|---|---|---|
| 1 | Creación del pipeline | `78028d8` buildspec.yml | Succeeded |
| 2 | Push (webhook) | `70466fd` prueba fallida intencional | **Failed** en Build |
| 3 | Push (webhook) | `1346ab1` revert | Succeeded |

Las ejecuciones 2 y 3 ya muestran que un push dispara el pipeline automáticamente y que una prueba fallida lo detiene. `apoyo_entrega2` se eliminará y no se integrará a `develop`.

## 4. Cambio de rama a `main`

> ⏳ **Pendiente.** Se hace después del PR `develop → main` (paso 3 del equipo). Mientras `main` no tenga `buildspec.yml`, cualquier ejecución sobre `main` falla.

Cambios (solo estos dos valores):

| Campo | Antes | Después |
|---|---|---|
| Etapa Source → acción `GitHub` → `BranchName` | `apoyo_entrega2` | `main` |
| Triggers → push → branches → includes | `apoyo_entrega2` | `main` |

Desde la consola: **CodePipeline → `blacklist-ci-pipeline` → Edit**. En la etapa Source, *Edit stage → Branch name = `main`*. En *Edit: Pipeline trigger*, cambiar el filtro de rama del push a `main`. Al final, **Save**.

Equivalente por CLI:

```bash
aws codepipeline get-pipeline --region us-east-2 --name blacklist-ci-pipeline > pipeline.json
# editar en pipeline.json los dos valores de la tabla y quitar el bloque "metadata"
aws codepipeline update-pipeline --region us-east-2 --cli-input-json file://pipeline.json
```

## 5. Verificación

```bash
# Rama de Source y del trigger (debe decir main en ambos)
aws codepipeline get-pipeline --region us-east-2 --name blacklist-ci-pipeline \
  --query '{Source:pipeline.stages[0].actions[0].configuration.BranchName,Trigger:pipeline.triggers[0].gitConfiguration.push[0].branches.includes,Etapas:pipeline.stages[].name}'

# Ejecuciones: tipo de disparo y commit
aws codepipeline list-pipeline-executions --region us-east-2 --pipeline-name blacklist-ci-pipeline \
  --query 'pipelineExecutionSummaries[].[status,trigger.triggerType,sourceRevisions[0].revisionId]' --output table
```

Resultado esperado tras un commit a `main`: una ejecución nueva con `triggerType = WebhookV2` cuyo commit es el último de `main`.

## 6. Evidencia para el documento de la entrega

Las capturas están en [`evidencias/`](evidencias/):

| Archivo | Contenido | Estado |
|---|---|---|
| `cp-conexion.png` | Conexión `blacklist-github`: proveedor GitHub, estado Available | ✅ |
| `cp-etapas.png` | Pipeline: etapas Source (GitHub, `main`) → Build (CodeBuild), sin Deploy | ⏳ Tras el cambio |
| `cp-source-main.png` | Configuración de la acción Source: repositorio y rama `main` | ⏳ Tras el cambio |
| `cp-trigger-main.png` | Trigger push filtrado a `main` | ⏳ Tras el cambio |
| `cp-ejecucion-main.png` | Ejecución disparada por un commit a `main` (WebhookV2) | ⏳ Tras el primer commit a `main` |
