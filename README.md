# Blacklist Microservice – Entrega 1 DevOps

Microservicio REST (Python + Flask + PostgreSQL) para gestionar la **lista negra global de emails**, desplegado manualmente en **AWS Elastic Beanstalk** con **AWS RDS**.

Universidad de los Andes · DevOps: Agilizando el Despliegue Continuo de Aplicaciones · Proyecto – Entrega 1

## Ramas

| Rama | Propósito |
|---|---|
| `main` | Versión entregada. Solo recibe merges desde `develop` |
| `develop` | Integración del equipo |
| `ft_post_blacklist` | Integrante 1 – Endpoint `POST /blacklists` |
| `ft_get_blacklist` | Integrante 2 – Endpoint `GET /blacklists/<email>` + Postman |
| `ft_infra_aws` | Integrante 3 – RDS + Elastic Beanstalk + health checks |
| `ft_estrategias_despliegue` | Integrante 4 – 4 estrategias de despliegue |
| `guia` | Implementación de referencia completa con todo el código (solo consulta, no se mergea) |

## Flujo de trabajo

1. Cada integrante trabaja en su rama `ft_*` (creada desde `develop`). Las ramas `main`, `develop` y `ft_*` arrancan sin código; la rama `guia` sirve de referencia.
2. Al terminar abre un **Pull Request `ft_* → develop`**, revisado por otro integrante.
3. Cuando todo está integrado y probado en AWS: **PR `develop → main`** para la entrega.

Las tareas están en la pestaña **Issues** (milestone *Entrega 1*).
