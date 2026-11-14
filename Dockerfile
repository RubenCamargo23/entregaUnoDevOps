# Imagen del microservicio blacklist para AWS Fargate.
# Se usa la réplica de Docker Hub en Amazon ECR Public para evitar los límites de descarga en CodeBuild.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY application.py .
COPY app/ app/

# Versión que reporta GET /health (la define el pipeline con el número de build)
ARG APP_VERSION=dev
RUN echo "$APP_VERSION" > VERSION

# Usuario sin privilegios dueño de /app (Flask crea ahí la carpeta instance/ si se usa SQLite)
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "application:application"]
