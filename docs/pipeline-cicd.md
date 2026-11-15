# Pipeline CI/CD – Entrega 3

Pipeline de integración y entrega continua del microservicio blacklist sobre AWS Fargate.

## Flujo

```
merge / push a main ──▶ AWS CodePipeline: blacklist-cicd-pipeline
                          ├─ Source:  GitHub (main) vía la conexión blacklist-github
                          ├─ Build:   AWS CodeBuild blacklist-cicd (buildspec-cd.yml)
                          │             pruebas unitarias → imagen Docker → Amazon ECR
                          └─ Deploy:  AWS CodeDeploy blacklist-ecs-app / blacklist-ecs-dg
                                        blue/green en ECS Fargate + prueba de humo + rollback
```

| Elemento | Configuración |
|---|---|
| Pipeline | `blacklist-cicd-pipeline` (CodePipeline V2, modo QUEUED) |
| Disparador | Push a la rama `main` (incluye el merge de pull requests) |
| Source | Acción `GitHub` (CodeStarSourceConnection), repositorio `RubenCamargo23/entregaUnoDevOps`, rama `main` |
| Build | Acción `PruebasEImagen` → proyecto CodeBuild `blacklist-cicd` (modo privilegiado) |
| Deploy | Acción `FargateBlueGreen` (CodeDeployToECS) con `taskdef.json`, `appspec.yaml` e `imageDetail.json` del build |
| Almacén de artefactos | S3 `blacklist-ci-artifacts-002493919126` |
| Rol del pipeline | `blacklist-cicd-pipeline-role` |

La definición completa del pipeline está en [`infra/codepipeline/blacklist-cicd-pipeline.json`](../infra/codepipeline/blacklist-cicd-pipeline.json). Para recrearlo o actualizarlo:

```bash
# Crear
aws codepipeline create-pipeline --cli-input-json file://infra/codepipeline/blacklist-cicd-pipeline.json --region us-east-2
# Actualizar
aws codepipeline update-pipeline --cli-input-json file://infra/codepipeline/blacklist-cicd-pipeline.json --region us-east-2
```

## Despliegue continuo (CodeDeploy blue/green)

| Evento | Qué ocurre |
|---|---|
| Install | Se crea el conjunto de tareas nuevo (green) con la imagen construida |
| AllowTestTraffic | El listener de pruebas `:8080` del balanceador apunta a las tareas nuevas |
| AfterAllowTestTraffic | La Lambda `CodeDeployHook_blacklist-smoke` valida `/health`, `POST /blacklists` y `GET /blacklists/<email>` |
| AllowTraffic | Si la prueba pasa, el listener de producción `:80` pasa a las tareas nuevas, sin caída |
| Fin | Las tareas anteriores se terminan 5 minutos después |

Si la prueba de humo o el despliegue fallan, CodeDeploy revierte automáticamente y producción sigue en la versión anterior.

## Pipeline de CI de la Entrega 2

`blacklist-ci-pipeline` queda **retirado**: se deshabilitó la transición hacia su etapa *Build*, para que cada commit a `main` ejecute un solo build (el de `blacklist-cicd-pipeline`, que ya incluye las pruebas unitarias). Se puede reactivar con:

```bash
aws codepipeline enable-stage-transition --pipeline-name blacklist-ci-pipeline --stage-name Build --transition-type Inbound --region us-east-2
```

## Verificación

1. Merge de un pull request a `main`.
2. CodePipeline → `blacklist-cicd-pipeline`: Source ✅ → Build ✅ → Deploy ✅ (≈ 8 minutos).
3. `curl http://blacklist-ecs-alb-493993814.us-east-2.elb.amazonaws.com/health` responde la versión nueva (`3.0.N`).
