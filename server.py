#!/usr/bin/env python3
"""
Servidor MCP para Kame ERP - Ferretería Bismarck SpA
Conecta Claude con la API de Kame para consultas y operaciones completas.
Versión 2.0 - Cobertura completa de todos los módulos de la API.
"""

import json
import sys
import os
import time
import requests
from typing import Any

# ─── Configuración ────────────────────────────────────────────────────────────
CLIENT_ID     = os.environ.get("KAME_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("KAME_CLIENT_SECRET", "")
BASE_URL      = os.environ.get("KAME_BASE_URL", "https://api.kame.cl")

# ─── Manejo de token ──────────────────────────────────────────────────────────
_token_cache = {"token": None, "expires_at": 0}

def get_token() -> str:
    """Obtiene token de Kame (Auth0), renovando si expiró (24h de validez)."""
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
    _token_cache["token"] = data.get("token") or data.get("access_token")
    _token_cache["expires_at"] = now + 23 * 3600
    return _token_cache["token"]

def headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}

def kame_get(endpoint: str, params: dict = None) -> Any:
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def kame_post(endpoint: str, body: dict) -> Any:
    resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers(), json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── Definición de herramientas ───────────────────────────────────────────────
TOOLS = [
    # ── VENTAS ────────────────────────────────────────────────────────────────
    {
        "name": "kame_informe_ventas",
        "description": "Obtiene el informe mensual de ventas (facturas, boletas, guías de despacho) para el mes y año indicados.",
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
        "name": "kame_detalle_venta",
        "description": "Obtiene el detalle completo de una venta específica (factura, boleta o guía) por su ID o folio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_venta": {"type": "string", "description": "ID o folio de la venta"},
            },
            "required": ["id_venta"],
        },
    },
    {
        "name": "kame_pdf_venta",
        "description": "Obtiene el PDF de una venta validada por el SII.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_venta": {"type": "string", "description": "ID o folio de la venta"},
            },
            "required": ["id_venta"],
        },
    },
    {
        "name": "kame_link_pago",
        "description": "Genera un enlace de pago Kame Pay para una venta.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_venta": {"type": "string", "description": "ID o folio de la venta"},
            },
            "required": ["id_venta"],
        },
    },
    # ── COTIZACIONES ──────────────────────────────────────────────────────────
    {
        "name": "kame_informe_cotizaciones",
        "description": "Obtiene el informe de cotizaciones emitidas para el mes y año indicados.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes (1-12)"},
                "anio": {"type": "integer", "description": "Año"},
            },
            "required": ["mes", "anio"],
        },
    },
    {
        "name": "kame_detalle_cotizacion",
        "description": "Obtiene el detalle completo de una cotización por su ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_cotizacion": {"type": "string", "description": "ID de la cotización"},
            },
            "required": ["id_cotizacion"],
        },
    },
    # ── PEDIDOS ───────────────────────────────────────────────────────────────
    {
        "name": "kame_detalle_pedido",
        "description": "Obtiene el detalle completo de un pedido por su ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_pedido": {"type": "string", "description": "ID del pedido"},
            },
            "required": ["id_pedido"],
        },
    },
    # ── COMPRAS ───────────────────────────────────────────────────────────────
    {
        "name": "kame_informe_compras",
        "description": "Obtiene el informe de compras para el mes y año indicados.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes (1-12)"},
                "anio": {"type": "integer", "description": "Año"},
            },
            "required": ["mes", "anio"],
        },
    },
    {
        "name": "kame_detalle_compra",
        "description": "Obtiene el detalle de un documento de compra por su ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_compra": {"type": "string", "description": "ID de la compra"},
            },
            "required": ["id_compra"],
        },
    },
    # ── INVENTARIO ────────────────────────────────────────────────────────────
    {
        "name": "kame_stock_general",
        "description": "Consulta el stock general de todos los artículos en todas las bodegas.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_stock_articulo",
        "description": "Consulta el stock de un artículo específico en todas las bodegas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "codigo_articulo": {"type": "string", "description": "Código del artículo en Kame"},
            },
            "required": ["codigo_articulo"],
        },
    },
    {
        "name": "kame_stock_bodega",
        "description": "Consulta el stock de todos los artículos en una bodega específica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "codigo_bodega": {"type": "string", "description": "Código o nombre de la bodega"},
            },
            "required": ["codigo_bodega"],
        },
    },
    {
        "name": "kame_stock_articulo_bodega",
        "description": "Consulta el stock de un artículo específico en una bodega específica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "codigo_articulo": {"type": "string", "description": "Código del artículo"},
                "codigo_bodega":   {"type": "string", "description": "Código de la bodega"},
            },
            "required": ["codigo_articulo", "codigo_bodega"],
        },
    },
    # ── COBROS Y PAGOS ────────────────────────────────────────────────────────
    {
        "name": "kame_cuentas_por_cobrar",
        "description": "Consulta el reporte de cuentas por cobrar (deudores/clientes con saldo pendiente).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_informe_cobros",
        "description": "Obtiene el informe de cobros realizados para el mes y año indicados.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes (1-12)"},
                "anio": {"type": "integer", "description": "Año"},
            },
            "required": ["mes", "anio"],
        },
    },
    {
        "name": "kame_cuentas_por_pagar",
        "description": "Consulta el reporte de cuentas por pagar (proveedores con saldo pendiente).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_informe_pagos",
        "description": "Obtiene el informe de pagos realizados para el mes y año indicados.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes (1-12)"},
                "anio": {"type": "integer", "description": "Año"},
            },
            "required": ["mes", "anio"],
        },
    },
    # ── MAESTROS ──────────────────────────────────────────────────────────────
    {
        "name": "kame_lista_articulos",
        "description": "Obtiene el catálogo completo de artículos/productos registrados en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_lista_clientes",
        "description": "Obtiene la lista de fichas de clientes y proveedores registrados en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_ficha_por_rut",
        "description": "Busca la ficha de un cliente o proveedor por su RUT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rut": {"type": "string", "description": "RUT del cliente/proveedor (ej: 12345678-9)"},
            },
            "required": ["rut"],
        },
    },
    {
        "name": "kame_lista_vendedores",
        "description": "Obtiene la lista de vendedores registrados en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_lista_precios_venta",
        "description": "Obtiene las listas de precios de venta configuradas en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_lista_precios_compra",
        "description": "Obtiene las listas de precios de compra configuradas en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_unidades_negocio",
        "description": "Obtiene la lista de unidades de negocio registradas en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ── CONTABILIDAD ──────────────────────────────────────────────────────────
    {
        "name": "kame_libro_diario",
        "description": "Consulta el libro diario contable de Kame (paginado por mes).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":    {"type": "integer", "description": "Mes (1-12)"},
                "anio":   {"type": "integer", "description": "Año"},
                "pagina": {"type": "integer", "description": "Número de página (por defecto 1)"},
            },
            "required": ["mes", "anio"],
        },
    },
]

# ─── Ejecución de herramientas ────────────────────────────────────────────────
def ejecutar(nombre: str, args: dict) -> str:
    try:
        # VENTAS
        if nombre == "kame_informe_ventas":
            data = kame_get("/ventas/informe", {"mes": args["mes"], "anio": args["anio"]})
        elif nombre == "kame_detalle_venta":
            data = kame_get(f"/ventas/{args['id_venta']}")
        elif nombre == "kame_pdf_venta":
            data = kame_get(f"/ventas/{args['id_venta']}/pdf")
        elif nombre == "kame_link_pago":
            data = kame_get(f"/ventas/{args['id_venta']}/kamepay")

        # COTIZACIONES
        elif nombre == "kame_informe_cotizaciones":
            data = kame_get("/cotizaciones/informe", {"mes": args["mes"], "anio": args["anio"]})
        elif nombre == "kame_detalle_cotizacion":
            data = kame_get(f"/cotizaciones/{args['id_cotizacion']}")

        # PEDIDOS
        elif nombre == "kame_detalle_pedido":
            data = kame_get(f"/pedidos/{args['id_pedido']}")

        # COMPRAS
        elif nombre == "kame_informe_compras":
            data = kame_get("/compras/informe", {"mes": args["mes"], "anio": args["anio"]})
        elif nombre == "kame_detalle_compra":
            data = kame_get(f"/compras/{args['id_compra']}")

        # INVENTARIO
        elif nombre == "kame_stock_general":
            data = kame_get("/inventario/stock")
        elif nombre == "kame_stock_articulo":
            data = kame_get(f"/inventario/stock/articulo/{args['codigo_articulo']}")
        elif nombre == "kame_stock_bodega":
            data = kame_get(f"/inventario/stock/bodega/{args['codigo_bodega']}")
        elif nombre == "kame_stock_articulo_bodega":
            data = kame_get(f"/inventario/stock/articulo/{args['codigo_articulo']}/bodega/{args['codigo_bodega']}")

        # COBROS Y PAGOS
        elif nombre == "kame_cuentas_por_cobrar":
            data = kame_get("/cobros/cuentas-por-cobrar")
        elif nombre == "kame_informe_cobros":
            data = kame_get("/cobros/informe", {"mes": args["mes"], "anio": args["anio"]})
        elif nombre == "kame_cuentas_por_pagar":
            data = kame_get("/pagos/cuentas-por-pagar")
        elif nombre == "kame_informe_pagos":
            data = kame_get("/pagos/informe", {"mes": args["mes"], "anio": args["anio"]})

        # MAESTROS
        elif nombre == "kame_lista_articulos":
            data = kame_get("/maestros/articulos")
        elif nombre == "kame_lista_clientes":
            data = kame_get("/maestros/fichas")
        elif nombre == "kame_ficha_por_rut":
            data = kame_get(f"/maestros/fichas/{args['rut']}")
        elif nombre == "kame_lista_vendedores":
            data = kame_get("/maestros/vendedores")
        elif nombre == "kame_lista_precios_venta":
            data = kame_get("/maestros/lista-precios-venta")
        elif nombre == "kame_lista_precios_compra":
            data = kame_get("/maestros/lista-precios-compra")
        elif nombre == "kame_unidades_negocio":
            data = kame_get("/maestros/unidades-negocio")

        # CONTABILIDAD
        elif nombre == "kame_libro_diario":
            params = {"mes": args["mes"], "anio": args["anio"], "pagina": args.get("pagina", 1)}
            data = kame_get("/contabilidad/libro-diario", params)

        else:
            return json.dumps({"error": f"Herramienta desconocida: {nombre}"})

        return json.dumps(data, ensure_ascii=False, indent=2)

    except requests.HTTPError as e:
        return json.dumps({"error": f"Error HTTP {e.response.status_code}: {e.response.text}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ─── Protocolo MCP (stdio JSON-RPC) ──────────────────────────────────────────
def send(obj: dict):
    print(json.dumps(obj, ensure_ascii=False), flush=True)

def handle(msg: dict):
    method = msg.get("method", "")
    mid    = msg.get("id")

    if method == "initialize":
        send({
            "jsonrpc": "2.0", "id": mid,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "kame-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {}},
            },
        })
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params    = msg.get("params", {})
        nombre    = params.get("name", "")
        args      = params.get("arguments", {})
        resultado = ejecutar(nombre, args)
        send({
            "jsonrpc": "2.0", "id": mid,
            "result": {
                "content": [{"type": "text", "text": resultado}],
                "isError": False,
            },
        })
    elif method == "notifications/initialized":
        pass
    else:
        if mid is not None:
            send({"jsonrpc": "2.0", "id": mid,
                  "error": {"code": -32601, "message": "Method not found"}})

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("⚠️  KAME_CLIENT_ID y KAME_CLIENT_SECRET no están configurados.", file=sys.stderr)
        print("   Edita el archivo claude_mcp_config.json con tus credenciales.", file=sys.stderr)

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
