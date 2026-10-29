#!/usr/bin/env python3
"""
Servidor MCP para Kame ERP - Ferretería Bismarck SpA
Versión 3.0 - URLs reales de la API oficial de Kame ERP (api.kameone.cl)
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
BASE_URL      = "https://api.kameone.cl/api"
AUTH_URL      = "https://auth.kameone.cl/oauth/token"   # Auth0
AUDIENCE      = "https://api.kameone.cl/api"

# ─── Manejo de token Auth0 ────────────────────────────────────────────────────
_token_cache = {"token": None, "expires_at": 0}

def get_token() -> str:
    """Obtiene token Auth0, renovando si expiró (24h de validez)."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    resp = requests.post(
        AUTH_URL,
        json={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "audience":      AUDIENCE,
            "grant_type":    "client_credentials",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 86400) - 300
    return _token_cache["token"]

def hdrs() -> dict:
    return {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def GET(path: str, params: dict = None) -> Any:
    resp = requests.get(f"{BASE_URL}{path}", headers=hdrs(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def POST(path: str, body: dict) -> Any:
    resp = requests.post(f"{BASE_URL}{path}", headers=hdrs(), json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── Helpers de fecha ─────────────────────────────────────────────────────────
def rango_mes(mes: int, anio: int):
    """Devuelve (fechaDesde, fechaHasta) para un mes dado."""
    desde = f"{anio}-{mes:02d}-01"
    if mes == 12:
        hasta = f"{anio}-12-31"
    else:
        hasta = (datetime(anio, mes + 1, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    return desde, hasta

# ─── Herramientas disponibles ─────────────────────────────────────────────────
TOOLS = [
    # ── VENTAS ────────────────────────────────────────────────────────────────
    {
        "name": "kame_informe_ventas",
        "description": "Obtiene el informe mensual de ventas (facturas, boletas, guías de despacho). Filtra por mes y año.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":      {"type": "integer", "description": "Mes (1-12)"},
                "anio":     {"type": "integer", "description": "Año, ej: 2025"},
                "pagina":   {"type": "integer", "description": "Página (default 1)"},
                "por_pagina": {"type": "integer", "description": "Registros por página (default 100)"},
            },
            "required": ["mes", "anio"],
        },
    },
    {
        "name": "kame_detalle_venta",
        "description": "Obtiene el detalle completo de una venta por tipo de documento y folio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tipo_documento": {
                    "type": "string",
                    "description": "Tipo: 'Factura Electrónica', 'Boleta Electrónica', 'Guía de Despacho Electrónica', 'Factura Exenta Electrónica', 'Liquidación Factura Electrónica'",
                },
                "folio": {"type": "string", "description": "Número de folio del documento"},
            },
            "required": ["tipo_documento", "folio"],
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
        "description": "Obtiene el detalle completo de una cotización por su número de folio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Número de folio de la cotización"},
            },
            "required": ["numero"],
        },
    },
    # ── PEDIDOS ───────────────────────────────────────────────────────────────
    {
        "name": "kame_detalle_pedido",
        "description": "Obtiene el detalle completo de un pedido por su número de folio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Número de folio del pedido"},
            },
            "required": ["numero"],
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
        "description": "Obtiene el detalle de un documento de compra por tipo, folio y RUT del proveedor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tipo_documento": {
                    "type": "string",
                    "description": "Tipo: 'Factura de Compra Electrónica', 'Factura Electrónica', 'Factura Exenta Electrónica'",
                },
                "folio":         {"type": "string", "description": "Número de folio"},
                "rut_proveedor": {"type": "string", "description": "RUT del proveedor (ej: 12345678-9)"},
            },
            "required": ["tipo_documento", "folio", "rut_proveedor"],
        },
    },
    # ── INVENTARIO ────────────────────────────────────────────────────────────
    {
        "name": "kame_stock_general",
        "description": "Consulta el stock consolidado de todos los artículos en todas las bodegas.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_stock_articulo",
        "description": "Consulta el stock consolidado de un artículo específico (por nombre o SKU) en todas las bodegas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nombre_articulo": {"type": "string", "description": "Nombre del artículo o SKU"},
            },
            "required": ["nombre_articulo"],
        },
    },
    {
        "name": "kame_stock_bodega",
        "description": "Consulta el stock de todos los artículos en una bodega específica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nombre_bodega": {"type": "string", "description": "Nombre de la bodega"},
            },
            "required": ["nombre_bodega"],
        },
    },
    {
        "name": "kame_stock_articulo_bodega",
        "description": "Consulta el stock de un artículo específico en una bodega específica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nombre_articulo": {"type": "string", "description": "Nombre del artículo o SKU"},
                "nombre_bodega":   {"type": "string", "description": "Nombre de la bodega"},
            },
            "required": ["nombre_articulo", "nombre_bodega"],
        },
    },
    # ── COBROS ────────────────────────────────────────────────────────────────
    {
        "name": "kame_cuentas_por_cobrar",
        "description": "Consulta las cuentas por cobrar (deudores) en un rango de fechas de vencimiento.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fecha_desde": {"type": "string", "description": "Fecha inicio vencimiento (YYYY-MM-DD)"},
                "fecha_hasta": {"type": "string", "description": "Fecha fin vencimiento (YYYY-MM-DD)"},
            },
            "required": ["fecha_desde", "fecha_hasta"],
        },
    },
    {
        "name": "kame_informe_cobros",
        "description": "Obtiene el informe de cobros realizados en un rango de fechas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fecha_desde": {"type": "string", "description": "Fecha inicio (YYYY-MM-DD)"},
                "fecha_hasta": {"type": "string", "description": "Fecha fin (YYYY-MM-DD)"},
            },
            "required": ["fecha_desde", "fecha_hasta"],
        },
    },
    # ── PAGOS ─────────────────────────────────────────────────────────────────
    {
        "name": "kame_cuentas_por_pagar",
        "description": "Consulta las cuentas por pagar (proveedores) en un rango de fechas de vencimiento.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fecha_desde": {"type": "string", "description": "Fecha inicio vencimiento (YYYY-MM-DD)"},
                "fecha_hasta": {"type": "string", "description": "Fecha fin vencimiento (YYYY-MM-DD)"},
            },
            "required": ["fecha_desde", "fecha_hasta"],
        },
    },
    {
        "name": "kame_informe_pagos",
        "description": "Obtiene el informe de pagos realizados en un rango de fechas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fecha_desde": {"type": "string", "description": "Fecha inicio (YYYY-MM-DD)"},
                "fecha_hasta": {"type": "string", "description": "Fecha fin (YYYY-MM-DD)"},
            },
            "required": ["fecha_desde", "fecha_hasta"],
        },
    },
    # ── MAESTROS ──────────────────────────────────────────────────────────────
    {
        "name": "kame_lista_articulos",
        "description": "Obtiene el catálogo de artículos. Puede filtrar por SKU específico.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "SKU específico para filtrar (opcional)"},
            },
        },
    },
    {
        "name": "kame_lista_clientes",
        "description": "Obtiene la lista de fichas de clientes y proveedores. Puede filtrar por RUT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rut": {"type": "string", "description": "RUT para filtrar (opcional, ej: 12345678-9)"},
            },
        },
    },
    {
        "name": "kame_lista_vendedores",
        "description": "Obtiene la lista de vendedores registrados en Kame.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kame_lista_precios_venta",
        "description": "Obtiene las listas de precios de venta. Puede filtrar por nombre de lista.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la lista de precio (opcional)"},
            },
        },
    },
    {
        "name": "kame_lista_precios_compra",
        "description": "Obtiene las listas de precios de compra. Puede filtrar por nombre de lista.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la lista de precio (opcional)"},
            },
        },
    },
    # ── CONTABILIDAD ──────────────────────────────────────────────────────────
    {
        "name": "kame_libro_diario",
        "description": "Consulta el libro diario contable para un rango de fechas (máximo un mes).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":    {"type": "integer", "description": "Mes (1-12)"},
                "anio":   {"type": "integer", "description": "Año"},
                "pagina": {"type": "integer", "description": "Página (default 1)"},
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
            desde, hasta = rango_mes(args["mes"], args["anio"])
            data = GET("/Documento/getInformeVentas", {
                "page": args.get("pagina", 1),
                "per_page": args.get("por_pagina", 100),
                "fechaDesde": desde,
                "fechaHasta": hasta,
            })
        elif nombre == "kame_detalle_venta":
            tipo = requests.utils.quote(args["tipo_documento"])
            data = GET(f"/Documento/getVenta/{tipo}/{args['folio']}")

        # COTIZACIONES
        elif nombre == "kame_informe_cotizaciones":
            desde, hasta = rango_mes(args["mes"], args["anio"])
            data = GET("/Documento/getInformeCotizaciones", {
                "page": 1, "per_page": 100,
                "fechaDesde": desde, "fechaHasta": hasta,
            })
        elif nombre == "kame_detalle_cotizacion":
            data = GET(f"/Documento/getCotizacion/{args['numero']}")

        # PEDIDOS
        elif nombre == "kame_detalle_pedido":
            data = GET(f"/Documento/getPedido/{args['numero']}")

        # COMPRAS
        elif nombre == "kame_informe_compras":
            desde, hasta = rango_mes(args["mes"], args["anio"])
            data = GET("/Documento/getInformeCompras", {
                "page": 1, "per_page": 100,
                "fechaDesde": desde, "fechaHasta": hasta,
            })
        elif nombre == "kame_detalle_compra":
            tipo = requests.utils.quote(args["tipo_documento"])
            data = GET(f"/Documento/getCompra/{tipo}/{args['folio']}/{args['rut_proveedor']}")

        # INVENTARIO
        elif nombre == "kame_stock_general":
            data = GET("/Inventario/getStock")
        elif nombre == "kame_stock_articulo":
            art = requests.utils.quote(args["nombre_articulo"])
            data = GET(f"/Inventario/getStockArticulo/{art}")
        elif nombre == "kame_stock_bodega":
            bod = requests.utils.quote(args["nombre_bodega"])
            data = GET(f"/Inventario/getStockBodega/{bod}")
        elif nombre == "kame_stock_articulo_bodega":
            art = requests.utils.quote(args["nombre_articulo"])
            bod = requests.utils.quote(args["nombre_bodega"])
            data = GET(f"/Inventario/getStockArticuloByBodega/{art}/{bod}")

        # COBROS
        elif nombre == "kame_cuentas_por_cobrar":
            data = GET("/Contabilidad/getCuentaxCobrar", {
                "page": 1, "per_page": 100,
                "fechaVencimientoDesde": args["fecha_desde"],
                "fechaVencimientoHasta": args["fecha_hasta"],
            })
        elif nombre == "kame_informe_cobros":
            data = GET("/Cobro/getInformeCobros", {
                "page": 1, "per_page": 100,
                "fechaDesde": args["fecha_desde"],
                "fechaHasta": args["fecha_hasta"],
            })

        # PAGOS
        elif nombre == "kame_cuentas_por_pagar":
            data = GET("/Contabilidad/getCuentaxPagar", {
                "page": 1, "per_page": 100,
                "fechaVencimientoDesde": args["fecha_desde"],
                "fechaVencimientoHasta": args["fecha_hasta"],
            })
        elif nombre == "kame_informe_pagos":
            data = GET("/Pago/getInformePagos", {
                "page": 1, "per_page": 100,
                "fechaDesde": args["fecha_desde"],
                "fechaHasta": args["fecha_hasta"],
            })

        # MAESTROS
        elif nombre == "kame_lista_articulos":
            params = {}
            if args.get("sku"): params["Sku"] = args["sku"]
            data = GET("/Maestro/getListArticulo", params or None)
        elif nombre == "kame_lista_clientes":
            params = {}
            if args.get("rut"): params["rut"] = args["rut"]
            data = GET("/Maestro/getListFicha", params or None)
        elif nombre == "kame_lista_vendedores":
            data = GET("/Maestro/getListVendedor")
        elif nombre == "kame_lista_precios_venta":
            params = {}
            if args.get("nombre"): params["nombre"] = args["nombre"]
            data = GET("/Maestro/getListaPrecioVenta", params or None)
        elif nombre == "kame_lista_precios_compra":
            params = {}
            if args.get("nombre"): params["nombre"] = args["nombre"]
            data = GET("/Maestro/getListaPrecioCompra", params or None)

        # CONTABILIDAD
        elif nombre == "kame_libro_diario":
            desde, hasta = rango_mes(args["mes"], args["anio"])
            data = GET("/Contabilidad/getLibroDiario", {
                "fechaDesde": desde,
                "fechaHasta": hasta,
                "page": args.get("pagina", 1),
                "per_page": 100,
            })

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
                "serverInfo": {"name": "kame-mcp", "version": "3.0.0"},
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
        print("   Configura las variables en claude_mcp_config.json", file=sys.stderr)

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
