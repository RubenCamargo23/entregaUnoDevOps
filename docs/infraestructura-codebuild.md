# Infraestructura AWS: integración continua con CodeBuild (Entrega 2)

Responsable: Diego Rojas ([@diegorojasd](https://github.com/diegorojasd)) · Rama: `ft_infra_ci` · Región: `us-east-2` (Ohio)

Este documento registra la infraestructura de integración continua: el bucket de artefactos, el proyecto de CodeBuild y su rol de servicio. También explica cómo verificarla y qué evidencia se adjunta al documento de la entrega. El proceso de CI lo define [`buildspec.yml`](../buildspec.yml): instala dependencias, ejecuta las pruebas unitarias, publica los reportes de pruebas y cobertura y, solo si las pruebas pasan, genera el artefacto. No despliega.

## Resumen

| Recurso | Nombre | Estado verificado |
|---|---|---|
| Bucket S3 de artefactos | `blacklist-ci-artifacts-002493919126` | Acceso público bloqueado, cifrado SSE-S3 (AES256) |
| Proyecto CodeBuild | `blacklist-ci` | Imagen `aws/codebuild/amazonlinux-x86_64-standard:5.0`, `buildspec.yml` del repositorio |
| Rol de servicio | `blacklist-codebuild-role` | Una política inline de permisos mínimos (`blacklist-codebuild-policy`) |
| Grupos de reportes | `blacklist-ci-pruebas-unitarias`, `blacklist-ci-cobertura` | Creados por el primer build |
| Logs | `/aws/codebuild/blacklist-ci` (CloudWatch Logs) | Habilitados |
| Build manual | Build **#4**, rama `ft_infra_ci` (commit `ae45411`) | **Succeeded**: 31/31 pruebas, cobertura de líneas 95,62 % |

```
GitHub (RubenCamargo23/entregaUnoDevOps) → CodeBuild blacklist-ci → S3 blacklist-ci-artifacts-002493919126
                                                  ├→ Reportes: pruebas (JUnit) y cobertura (Cobertura XML)
                                                  └→ CloudWatch Logs
```

## 1. Bucket S3 de artefactos

| Parámetro | Valor |
|---|---|
| Nombre | `blacklist-ci-artifacts-002493919126` (el sufijo es el ID de la cuenta, para que el nombre sea único) |
| Región | `us-east-2` |
| Acceso público | Bloqueado (las cuatro opciones de *Block Public Access* activas) |
| Cifrado | SSE-S3 (AES256) |

Contenido:

- `manual/<build-id>/blacklist-artifact.zip`: artefacto del build manual.
- `blacklist-ci-pipelin/…`: artefactos que deja `blacklist-ci-pipeline` (ver [sección 5](#5-supuestos-y-limitaciones)).

## 2. Proyecto CodeBuild `blacklist-ci`

| Parámetro | Valor |
|---|---|
| Imagen | `aws/codebuild/amazonlinux-x86_64-standard:5.0` (Linux Container, 2 vCPU / 4 GiB) |
| Runtime | Python 3.12 (`runtime-versions` en `buildspec.yml`) |
| Buildspec | `buildspec.yml` de la raíz del repositorio |
| Rol de servicio | `blacklist-codebuild-role` |
| Reportes | `pruebas-unitarias` (JUnit XML) y `cobertura` (Cobertura XML), definidos en `buildspec.yml` |
| Logs | CloudWatch Logs, grupo `/aws/codebuild/blacklist-ci` |
| Fuente y artefactos configurados | `AWS CodePipeline` (ver [sección 5](#5-supuestos-y-limitaciones)) |

### Build manual

El build manual se lanzó contra el mismo proyecto, indicando la fuente GitHub y el destino S3 en la propia ejecución. Así no se modificó la configuración del proyecto:

```bash
aws codebuild start-build --region us-east-2 --project-name blacklist-ci \
  --source-type-override GITHUB \
  --source-location-override https://github.com/RubenCamargo23/entregaUnoDevOps.git \
  --source-version ft_infra_ci \
  --artifacts-override type=S3,location=blacklist-ci-artifacts-002493919126,path=manual,name=blacklist-artifact.zip,packaging=ZIP,namespaceType=BUILD_ID
```

El repositorio es público, así que CodeBuild lo clona sin credenciales de GitHub.

Resultado del build **#4** (2026-10-31, iniciado por `devops-cli`):

| Fase | Estado | Duración |
|---|---|---|
| PROVISIONING | Succeeded | 3 s |
| DOWNLOAD_SOURCE | Succeeded | 3 s |
| INSTALL | Succeeded | 16 s |
| PRE_BUILD | Succeeded | < 1 s |
| BUILD (pytest) | Succeeded | 2 s |
| POST_BUILD (artefacto) | Succeeded | < 1 s |
| UPLOAD_ARTIFACTS | Succeeded | 1 s |

- **Pruebas** (`blacklist-ci-pruebas-unitarias`): 31 casos, 31 exitosos, 100 %.
- **Cobertura** (`blacklist-ci-cobertura`): líneas 95,62 % (131/137).
- **Artefacto**: `s3://blacklist-ci-artifacts-002493919126/manual/7b8e1d24-e8f0-4f7e-b907-c93704971e95/blacklist-artifact.zip` (5,2 KB). Contiene `application.py`, `requirements.txt`, `Procfile`, `app/`, `.ebextensions/` y `VERSION` (`2.0.4`).

## 3. Rol de servicio `blacklist-codebuild-role`

- **Relación de confianza**: solo `codebuild.amazonaws.com`.
- **Permisos**: no tiene políticas administradas. Usa una sola política inline, `blacklist-codebuild-policy`, en la que cada permiso está limitado a los recursos de este proyecto:

| Servicio | Acciones | Recurso |
|---|---|---|
| CloudWatch Logs | `CreateLogGroup`, `CreateLogStream`, `PutLogEvents` | `log-group:/aws/codebuild/blacklist-ci*` |
| S3 | `GetObject`, `GetObjectVersion`, `PutObject`, `GetBucketLocation`, `GetBucketAcl` | Solo el bucket `blacklist-ci-artifacts-002493919126` y sus objetos |
| CodeBuild (reportes) | `CreateReportGroup`, `CreateReport`, `UpdateReport`, `BatchPutTestCases`, `BatchPutCodeCoverages` | `report-group/blacklist-ci-*` |

No incluye permisos sobre Elastic Beanstalk, EC2 ni RDS, porque el CI no despliega.

## 4. Verificación (CLI, solo lectura)

```bash
# Proyecto
aws codebuild batch-get-projects --region us-east-2 --names blacklist-ci \
  --query 'projects[0].{Imagen:environment.image,Buildspec:source.buildspec,Rol:serviceRole,Logs:logsConfig.cloudWatchLogs.groupName}'

# Builds (estado, rama/commit y quién los inició)
aws codebuild list-builds-for-project --region us-east-2 --project-name blacklist-ci
aws codebuild batch-get-builds --region us-east-2 --ids <id> \
  --query 'builds[].[buildNumber,buildStatus,sourceVersion,initiator]' --output table

# Bucket
aws s3 ls s3://blacklist-ci-artifacts-002493919126/manual/ --recursive
aws s3api get-public-access-block --bucket blacklist-ci-artifacts-002493919126

# Rol
aws iam get-role-policy --role-name blacklist-codebuild-role --policy-name blacklist-codebuild-policy
```

## 5. Supuestos y limitaciones

- **El proyecto también lo usa un pipeline.** Antes de esta verificación se creó `blacklist-ci-pipeline` (CodePipeline: GitHub → CodeBuild `blacklist-ci`), que apunta a la rama `apoyo_entrega2`. Por eso la fuente y los artefactos configurados en el proyecto son `AWS CodePipeline`, y no GitHub y S3 directamente. Los builds #1 (Succeeded), #2 (Failed, prueba fallida intencional) y #3 (Succeeded, revert) los lanzó ese pipeline.
- **Por qué el build manual usa overrides.** Cambiar la fuente del proyecto a GitHub habría dejado sin funcionar el pipeline. Los overrides cumplen el criterio (fuente GitHub, artefacto en S3) sin tocar la configuración compartida.
- **La rama `apoyo_entrega2` se eliminará y no se integrará a `develop`.** Su código (`buildspec.yml`, pruebas, aplicación) es idéntico al de `ft_infra_ci`. Por eso el build manual de evidencia se ejecutó desde `ft_infra_ci`. Antes de borrar esa rama hay que cambiar la rama de origen del pipeline (paso 4 del equipo: pipeline a `main`); si no, el pipeline fallará en la etapa Source.
- El build #2 fallido sirve como antecedente de que el pipeline detiene la entrega cuando una prueba falla. La evidencia formal de ejecución exitosa y fallida corresponde al paso 5 del equipo.
- La infraestructura se creó manualmente; no hay plantilla de IaC en el repositorio.

## 6. Evidencia para el documento de la entrega

Las capturas están en [`evidencias/`](evidencias/):

| Archivo | Contenido |
|---|---|
| `cb-proyecto.png` | `blacklist-ci` → Project details: fuente, imagen `amazonlinux-x86_64-standard:5.0`, rol de servicio |
| `cb-buildspec-logs.png` | Project details: buildspec `buildspec.yml`, artefactos y CloudWatch Logs |
| `cb-build-history.png` | Build history: build #4 manual (`ft_infra_ci`, `devops-cli`) y #1–#3 del pipeline |
| `cb-build-manual.png` | Build #4: Succeeded, commit `ae45411`, todas las fases en Succeeded y los dos reportes |
| `cb-reporte-pruebas.png` | Reporte `blacklist-ci-pruebas-unitarias` del build #4: 31 casos, 100 % |
| `cb-reporte-cobertura.png` | Reporte `blacklist-ci-cobertura` del build #4: líneas 95,62 % (131/137) |
| `s3-artefacto.png` | `blacklist-artifact.zip` del build #4 en `s3://blacklist-ci-artifacts-002493919126/manual/` |
| `iam-rol-1.png` | `blacklist-codebuild-role` → política inline, líneas 1–25 (Logs y S3) |
| `iam-rol-2.png` | Misma política, líneas 13–39 (S3 y reportes de CodeBuild) |

Capturas tomadas el 2026-10-31.
