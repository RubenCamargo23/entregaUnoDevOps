# Infraestructura AWS: RDS y Elastic Beanstalk (Entrega 2)

Responsable: Diego Rojas ([@diegorojasd](https://github.com/diegorojasd)) · Rama: `ft_infra_ci` · Región: `us-east-2` (Ohio)

La infraestructura de la Entrega 1 fue eliminada. Para la Entrega 2 se volvió a crear el ambiente sobre el que se despliega la aplicación. Este documento registra qué se configuró, cómo verificarlo y qué evidencia se adjunta al documento de la entrega.

## Resumen

| Recurso | Nombre | Estado esperado |
|---|---|---|
| Ambiente Elastic Beanstalk | `blacklist-env` | Health **Green**, versión **v2.0.0** |
| URL del ambiente | http://blacklist-devops-e1.us-east-2.elasticbeanstalk.com | `GET /health` → `200` |
| Base de datos RDS | `blacklist-db` | *Available*, sin acceso público |
| Aplicación Elastic Beanstalk | `blacklist-app` | — |
| Security Group de RDS | `blacklist-db-sg` (`sg-075c2c7d98898c6a9`) | Entrada 5432 solo desde `blacklist-app-sg` |
| Security Group de las instancias | `blacklist-app-sg` (`sg-077c4a8c3deab5946`), más el SG que crea Beanstalk | Asignado a las instancias del ambiente |

```
Cliente (Postman) → ALB → Auto Scaling Group (3–6 EC2, Python 3.12 / AL2023) → RDS PostgreSQL (privada)
```

Diagrama: [`arquitectura.png`](arquitectura.png).

## 1. RDS PostgreSQL

### Configuración

| Parámetro | Valor |
|---|---|
| Motor | PostgreSQL |
| Plantilla | Capa gratuita (*Free tier*) |
| Identificador | `blacklist-db` |
| Clase de instancia | `db.t3.micro` |
| Almacenamiento | 20 GB |
| Acceso público | **No** |
| Base de datos inicial | `blacklist` |
| Usuario maestro | Se configura en el ambiente como `RDS_USERNAME` (no se documenta aquí) |
| Security Group | Entrada TCP **5432** solo desde el SG de las instancias de Beanstalk (sin reglas `0.0.0.0/0`) |

La aplicación crea la tabla `blacklist` al arrancar (`db.create_all()`), así que no hace falta ningún script de migración.

### Verificación (consola)

1. **RDS → Databases → `blacklist-db`**:
   - *Status*: `Available`.
   - Pestaña *Connectivity & security*: **Publicly accessible = No**. Anotar el SG en *VPC security groups*.
   - Pestaña *Configuration*: engine PostgreSQL, clase `db.t3.micro`, 20 GB, *DB name* `blacklist`.
2. **EC2 → Security Groups → SG de RDS → Inbound rules**: una sola regla `PostgreSQL / TCP 5432` cuyo *Source* es el SG de las instancias de Beanstalk (`sg-…`), no un rango CIDR.

### Verificación (CLI, solo lectura)

```bash
aws rds describe-db-instances --region us-east-2 --db-instance-identifier blacklist-db \
  --query 'DBInstances[0].{Estado:DBInstanceStatus,Motor:Engine,Clase:DBInstanceClass,GB:AllocatedStorage,Publica:PubliclyAccessible,DB:DBName,SG:VpcSecurityGroups[].VpcSecurityGroupId}'

aws ec2 describe-security-groups --region us-east-2 --group-ids <SG_RDS> \
  --query 'SecurityGroups[0].IpPermissions'
```

Resultado esperado: `Publica: false` y, en `IpPermissions`, el puerto 5432 con `UserIdGroupPairs` (el SG de las instancias) y `IpRanges` vacío.

## 2. Elastic Beanstalk

### Configuración

La mayor parte viene del repositorio, en [`.ebextensions/01_environment.config`](../.ebextensions/01_environment.config), y se aplica al crear el ambiente:

| Parámetro | Valor | Origen |
|---|---|---|
| Plataforma | Python 3.12 en Amazon Linux 2023 | Consola (al crear) |
| Tipo de ambiente | Con balanceo de carga (alta disponibilidad) | `.ebextensions` |
| Balanceador | Application Load Balancer | `.ebextensions` |
| Instancias | `t3.micro` | Consola (al crear) |
| Auto Scaling | Mín **3**, máx **6** | `.ebextensions` |
| Health check | `GET /health`, cada 15 s, timeout 5 s, 3 respuestas sanas / 5 fallidas, HTTP 200 | `.ebextensions` |
| Reporte de salud | Mejorado (*enhanced*) | `.ebextensions` |
| WSGI | `application:application` (Gunicorn, `Procfile`) | `.ebextensions` / `Procfile` |

### Propiedades del entorno

En *Configuration → Updates, monitoring, and logging → Environment properties*, que [`app/config.py`](../app/config.py) lee al arrancar:

| Variable | Contenido |
|---|---|
| `RDS_HOSTNAME` | Endpoint de `blacklist-db` |
| `RDS_PORT` | `5432` |
| `RDS_DB_NAME` | `blacklist` |
| `RDS_USERNAME` | Usuario maestro de RDS |
| `RDS_PASSWORD` | Contraseña maestra de RDS |
| `JWT_SECRET_KEY` | Clave para firmar el token (32 caracteres o más) |

> ⚠️ Los valores no se versionan ni se copian en este documento. En las capturas, tapa `RDS_PASSWORD`, `JWT_SECRET_KEY` y, si es posible, `RDS_HOSTNAME`.

Si falta `RDS_HOSTNAME` (y no hay `DATABASE_URL`), la aplicación cae a SQLite local. En ese caso, cada instancia tendría su propia base de datos y la colección de Postman fallaría de forma intermitente. Revisa que las seis variables estén definidas.

### Verificación (consola)

1. **Elastic Beanstalk → Environments → `blacklist-env` → Overview**: *Health* `Ok` (Green), *Running version* `v2.0.0` y *Platform* Python 3.12 / AL2023.
2. **Configuration → Capacity**: *Environment type* `Load balanced`, *Instances* Min `3` / Max `6`, *Instance types* `t3.micro`.
3. **Configuration → Load balancer**: tipo `Application`. En *Processes*, `default` con *Health check path* `/health`.
4. **Configuration → Updates, monitoring, and logging → Environment properties**: están las seis variables de la tabla anterior.
5. **Health**: 3 instancias en `Ok`.

### Verificación (CLI, solo lectura)

```bash
aws elasticbeanstalk describe-environments --region us-east-2 --environment-names blacklist-env \
  --query 'Environments[0].{Estado:Status,Salud:Health,Version:VersionLabel,Plataforma:SolutionStackName,CNAME:CNAME}'

aws elasticbeanstalk describe-configuration-settings --region us-east-2 \
  --application-name blacklist-app --environment-name blacklist-env \
  --query 'ConfigurationSettings[0].OptionSettings[?OptionName==`MinSize`||OptionName==`MaxSize`||OptionName==`HealthCheckPath`||OptionName==`LoadBalancerType`].[Namespace,OptionName,Value]' \
  --output table
```

> El segundo comando también devuelve las propiedades del entorno si se quita el filtro `--query`. **No lo ejecutes sin filtro**, porque imprimiría `RDS_PASSWORD` y `JWT_SECRET_KEY`.

### Verificación (HTTP)

```bash
curl -s http://blacklist-devops-e1.us-east-2.elasticbeanstalk.com/health
# Esperado: {"status": "ok", "version": "2.0.0"}
```

## 3. Postman contra el nuevo ambiente

- **Colección**: [`postman/blacklist.postman_collection.json`](../postman/blacklist.postman_collection.json), con 8 requests y **13 tests**.
- **Environment**: `postman/blacklist-aws.postman_environment.json`. El `base_url` no cambia: el ambiente nuevo conserva el CNAME `blacklist-devops-e1`.
- **Token**: si `JWT_SECRET_KEY` del ambiente nuevo es distinta a la de la E1, el `token` guardado ya no sirve (los requests protegidos responden 401). En ese caso, genera uno nuevo con la misma clave y actualiza la variable `token` **solo en tu Postman local**:

  ```bash
  JWT_SECRET_KEY="$JWT_SECRET_KEY" python scripts/generate_token.py
  ```

- **Ejecución**: *Collection Runner* con el environment `blacklist-aws`, o:

  ```bash
  npx newman run postman/blacklist.postman_collection.json \
    -e postman/blacklist-aws.postman_environment.json \
    --env-var "token=$TOKEN"
  ```

  Resultado esperado: **13/13 tests en verde**, 0 fallidos.

## 4. Evidencia para el documento de la entrega

Guardar las capturas en [`evidencias/`](evidencias/):

| Archivo | Contenido |
|---|---|
| `eb-overview.png` | `blacklist-env` → Overview: Health Ok (Green), versión v2.0.0, Python 3.12 en AL2023 |
| `eb-capacidad.png` | Configuration → Infrastructure: Auto Scaling mín 3 / máx 6, `t3.micro` |
| `eb-health-check.png` | Target group del ALB → Health checks: `/health`, 15 s, 3/5, HTTP 200, 3 targets Healthy |
| `eb-variables.png` | Configuration → Environment properties: `RDS_*` y `JWT_SECRET_KEY` (valores sensibles tapados), tipo Load balanced |
| `eb-instancias.png` | Health & monitoring: 3 instancias en Ok, 100 % respuestas 2xx |
| `rds-blacklist-db.png` | RDS → `blacklist-db` → Configuration: Available, PostgreSQL 18.3, `db.t3.micro`, 20 GiB, DB `blacklist` |
| `rds-conectividad.png` | RDS → Connectivity & security: **Publicly accessible = No**, SG `blacklist-db-sg` |
| `sg-rds.png` | Inbound rules de `blacklist-db-sg`: una regla, PostgreSQL 5432 desde `blacklist-app-sg` |
| `postman-13-13.png` | Newman contra el ambiente: 13/13 assertions, 8 requests, 0 fallidos |
| `postman-newman.txt` | Salida completa de newman de la misma corrida |

Capturas tomadas el 2026-10-31. En las de la consola se taparon el endpoint de RDS, el usuario maestro, `RDS_PASSWORD` y `JWT_SECRET_KEY` antes de tomarlas.

## 5. Supuestos y limitaciones

- La infraestructura se creó manualmente desde la consola; no hay plantilla de IaC en el repositorio.
- Los nombres de la aplicación Beanstalk y de los Security Groups se confirmaron con la AWS CLI el 2026-10-31.
- El token de Postman es estático y no expira (`JWT_ACCESS_TOKEN_EXPIRES = False`). Depende únicamente de `JWT_SECRET_KEY`.
- La capa gratuita de RDS y de EC2 tiene límites de horas mensuales. Con 3 instancias `t3.micro` se superan las 750 h gratuitas de EC2, así que hay que eliminar los recursos al terminar la entrega (ver README → *Limpieza*).
