"""Prueba de humo del despliegue blue/green (hook AfterAllowTestTraffic de AWS CodeDeploy).

Llama a la nueva versión por el listener de pruebas del balanceador (puerto 8080), antes de que reciba
tráfico real, y le informa a CodeDeploy si pasó o no. Si falla, CodeDeploy revierte el despliegue.
"""
import json
import os
import time
import urllib.request
import uuid

import boto3

codedeploy = boto3.client("codedeploy")
ssm = boto3.client("ssm")

TEST_URL = os.environ["TEST_URL"]
PROD_URL = os.environ["PROD_URL"]
TOKEN_PARAM = os.environ["TOKEN_PARAM"]


def _call(method, path, token=None, body=None, base=TEST_URL):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, {}


def _wait_for_new_version(max_wait=90):
    """El balanceador tarda unos segundos en aplicar el cambio del listener de pruebas:
    espera a que el puerto de pruebas responda una versión distinta a la de producción."""
    prod_version = _call("GET", "/health", base=PROD_URL)[1].get("version")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        test_version = _call("GET", "/health")[1].get("version")
        if test_version and test_version != prod_version:
            print(f"Versión en producción: {prod_version} · versión en pruebas: {test_version}")
            return
        time.sleep(5)
    print(f"El puerto de pruebas sigue respondiendo la versión de producción ({prod_version})")


def smoke_test():
    _wait_for_new_version()
    token = ssm.get_parameter(Name=TOKEN_PARAM, WithDecryption=True)["Parameter"]["Value"]
    email = f"smoke.{uuid.uuid4().hex[:8]}@example.com"

    checks = [
        ("GET /health", _call("GET", "/health"), 200),
        ("POST /blacklists", _call("POST", "/blacklists", token, {"email": email, "app_uuid": str(uuid.uuid4()), "blocked_reason": "Prueba de humo"}), 201),
        ("GET /blacklists/<email>", _call("GET", f"/blacklists/{email}", token), 200),
    ]
    failures = [f"{name}: HTTP {status} (esperado {expected})" for name, (status, _), expected in checks if status != expected]
    for name, (status, body), _ in checks:
        print(f"{name} -> {status} {body}")
    return failures


def lambda_handler(event, context):
    try:
        failures = smoke_test()
    except Exception as exc:  # cualquier error de red o de configuración cuenta como fallo
        failures = [f"Error ejecutando la prueba de humo: {exc}"]

    status = "Failed" if failures else "Succeeded"
    print(f"Resultado de la prueba de humo: {status} {failures}")
    codedeploy.put_lifecycle_event_hook_execution_status(
        deploymentId=event["DeploymentId"],
        lifecycleEventHookExecutionId=event["LifecycleEventHookExecutionId"],
        status=status,
    )
    return {"status": status, "failures": failures}
