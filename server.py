#!/usr/bin/env python3
"""
Servidor MCP para Kame ERP - Ferretería Bismarck SpA
Conecta Claude con la API de Kame para consultas de ventas, stock e informes.
"""

import json
import sys
import os
import time
import requests
from datetime import datetime, timedelta
from typing import Any

# ─── Configuración ────────────────────────────────────────────────────────────
CLIENT_ID     = os.environ.get("KAME_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("KAME_CLIENT_SECRET", "")
BASE_URL      = "https://api.kame.cl"   # Ajustar si Kame entrega otra URL base

# ─── Manejo de token ──────────────────────────────────────────────────────────
_token_cache = {"token": None, "expires_at": 0}

def get_token() -> str:
    """Obtiene token de Kame, renovando si expiró (24h de validez)."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    resp = requests.post(
        f"{BASE_URL}/auth/token",
        json={"clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["token"]
    _token_cache["expires_at"] = now + 23 * 3600  # renovar 1h antes
    return _token_cache["token"]

def kame_get(endpoint: str, params: dict = None) -> Any:
    """Hace GET a la API de Kame con autenticación automática."""
    headers = {"Authorization": f"Bearer {get_token()}"}
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── Herramientas disponibles ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "kame_informe_ventas",
        "description": "Obtiene el informe mensual de ventas de Kame ERP. Retorna documentos emitidos (facturas, boletas, guías) para el mes y año indicados.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes (1-12)"},
                "anio": {"type": "integer", "description": "Año, ej: 2025"},
            },
            "required": ["mes", "anio"],
        },
    },
    {
        "name": "kame_stock",
        "description": "Consulta el stock disponible en Kame ERP. Puede filtrar por código de artículo o bodega.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "articulo": {"type": "string", "description": "Código o nombre del artículo (opcional)"},
                "bodega":   {"type": "string", "description": "Nombre o código de bodega (opcional)"},
            },
        },
    },
    {
        "name": "kame_cuentas_por_cobrar",
        "description": "Consulta el reporte de cuentas por cobrar (deudores) en Kame ERP.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_cuentas_por_pagar",
        "description": "Consulta el reporte de cuentas por pagar (proveedores) en Kame ERP.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_lista_articulos",
        "description": "Obtiene el catálogo completo de artículos/productos registrados en Kame ERP.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_lista_clientes",
        "description": "Obtiene la lista de fichas de clientes registrados en Kame ERP.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_detalle_venta",
        "description": "Obtiene el detalle completo de una venta específica por su ID o folio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_venta": {"type": "string", "description": "ID o folio de la venta"},
            },
            "required": ["id_venta"],
        },
    },
]

# ─── Ejecución de herramientas ────────────────────────────────────────────────
def ejecutar_herramienta(nombre: str, args: dict) -> str:
    try:
        if nombre == "kame_informe_ventas":
            data = kame_get("/ventas/informe", {"mes": args["mes"], "anio": args["anio"]})
        elif nombre == "kame_stock":
            params = {}
            if args.get("articulo"): params["articulo"] = args["articulo"]
            if args.get("bodega"):   params["bodega"]   = args["bodega"]
            data = kame_get("/inventario/stock", params)
        elif nombre == "kame_cuentas_por_cobrar":
            data = kame_get("/contabilidad/cuentas-por-cobrar")
        elif nombre == "kame_cuentas_por_pagar":
            data = kame_get("/contabilidad/cuentas-por-pagar")
        elif nombre == "kame_lista_articulos":
            data = kame_get("/maestros/articulos")
        elif nombre == "kame_lista_clientes":
            data = kame_get("/maestros/fichas")
        elif nombre == "kame_detalle_venta":
            data = kame_get(f"/ventas/{args['id_venta']}")
        else:
            return json.dumps({"error": f"Herramienta desconocida: {nombre}"})

        return json.dumps(data, ensure_ascii=False, indent=2)

    except requests.HTTPError as e:
        return json.dumps({"error": f"Error HTTP {e.response.status_code}: {e.response.text}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ─── Protocolo MCP (stdio JSON-RPC) ──────────────────────────────────────────
def send(obj: dict):
    print(json.dumps(obj), flush=True)

def handle(msg: dict):
    method = msg.get("method", "")
    mid    = msg.get("id")

    if method == "initialize":
        send({
            "jsonrpc": "2.0", "id": mid,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "kame-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        })

    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})

    elif method == "tools/call":
        params   = msg.get("params", {})
        nombre   = params.get("name", "")
        args     = params.get("arguments", {})
        resultado = ejecutar_herramienta(nombre, args)
        send({
            "jsonrpc": "2.0", "id": mid,
            "result": {
                "content": [{"type": "text", "text": resultado}],
                "isError": False,
            },
        })

    elif method == "notifications/initialized":
        pass  # no requiere respuesta

    else:
        if mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}})

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("⚠️  KAME_CLIENT_ID y KAME_CLIENT_SECRET deben estar configurados.", file=sys.stderr)
        print("   Edita el archivo .env o configura las variables de entorno.", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            handle(msg)
        except json.JSONDecodeError:
            pass

if __name__ == "__main__":
    main()
