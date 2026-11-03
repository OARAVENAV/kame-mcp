#!/usr/bin/env python3
"""
Servidor MCP para Kame ERP - Ferretería Bismarck SpA
Versión 3.1 - URLs reales de la API oficial de Kame ERP (api.kameone.cl)
+ Órdenes de compra: crear, cerrar y OC referenciadas en facturas
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
AUTH_URL      = "https://api.kameone.cl/oauth/token"    # Auth0
AUDIENCE      = "https://api.kameone.cl/api"

# Datos para crear/cerrar órdenes de compra
KAME_USUARIO          = os.environ.get("KAME_USUARIO", "")   # correo del usuario Kame que registra la OC
BODEGA_DEFAULT        = os.environ.get("KAME_BODEGA_DEFAULT", "Bismarck")
UNIDAD_NEGOCIO_DEFAULT = os.environ.get("KAME_UNIDAD_NEGOCIO_DEFAULT", "Casa Matriz")
TASA_IVA              = 0.19

# En el informe de compras Kame marca las referencias a OC con el código "23";
# en el detalle aparecen como "Orden de Compra". 801 es el código SII de OC.
CODIGOS_REF_OC = {"23", "801"}

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
    if not resp.text.strip():
        return {}
    try:
        return resp.json()
    except ValueError:
        return {"respuesta": resp.text}

def GET_TODAS_LAS_PAGINAS(path: str, params: dict, max_paginas: int = 50) -> list:
    """Recorre todas las páginas de un informe paginado y devuelve los items juntos."""
    items, pagina = [], 1
    while pagina <= max_paginas:
        data = GET(path, {**params, "page": pagina, "per_page": 100})
        lote = data.get("items", []) if isinstance(data, dict) else []
        items.extend(lote)
        if len(lote) < 100:
            break
        pagina += 1
    return items

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
    {
        "name": "kame_oc_referenciadas",
        "description": (
            "Lista las órdenes de compra que aparecen referenciadas en las facturas de compra del mes "
            "(la API de Kame no permite listar OC directamente). Agrupa por factura e indica qué facturas "
            "no referencian ninguna OC. No muestra OC que todavía no tienen factura."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes de las facturas (1-12)"},
                "anio": {"type": "integer", "description": "Año"},
            },
            "required": ["mes", "anio"],
        },
    },
    # ── ÓRDENES DE COMPRA ─────────────────────────────────────────────────────
    {
        "name": "kame_crear_orden_compra",
        "description": (
            "Crea una orden de compra en Kame. Calcula neto, IVA, total y cuotas automáticamente. "
            "IMPORTANTE: con confirmar=false (por defecto) NO envía nada: devuelve una vista previa con los "
            "montos para revisarla con el usuario. Solo usar confirmar=true después de que el usuario "
            "apruebe explícitamente esa vista previa."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rut_proveedor":  {"type": "string", "description": "RUT del proveedor (ej: 77.101.910-2)"},
                "razon_social":   {"type": "string", "description": "Razón social del proveedor"},
                "comentario":     {"type": "string", "description": "Glosa de la OC (máx. 255 caracteres)"},
                "lineas": {
                    "type": "array",
                    "description": "Líneas de la OC",
                    "items": {
                        "type": "object",
                        "properties": {
                            "descripcion":     {"type": "string", "description": "Descripción del ítem"},
                            "sku":             {"type": "string", "description": "SKU del artículo (obligatorio si es inventariable)"},
                            "cantidad":        {"type": "number"},
                            "precio_unitario": {"type": "number", "description": "Precio unitario neto (sin IVA)"},
                            "porc_descuento":  {"type": "number", "description": "Descuento % de la línea (default 0)"},
                            "unidad_medida":   {"type": "string", "description": "Default 'UN'"},
                            "tipo_articulo":   {"type": "string", "enum": ["ARTICULO", "SERVICIO", "ACTIVOFIJO"], "description": "Default 'ARTICULO'"},
                            "descripcion_detallada": {"type": "string"},
                        },
                        "required": ["descripcion", "cantidad", "precio_unitario"],
                    },
                },
                "fecha":          {"type": "string", "description": "Fecha de la OC YYYY-MM-DD (default hoy)"},
                "fecha_recepcion": {"type": "string", "description": "Fecha de recepción esperada YYYY-MM-DD (default = fecha)"},
                "documento": {
                    "type": "string",
                    "description": "Documento esperado: 'Factura Electrónica' (default), 'Factura Exenta Electrónica', 'Factura de Compra Electrónica', 'Factura', 'Factura Exenta'",
                },
                "forma_pago":     {"type": "string", "enum": ["contado", "credito"], "description": "Default 'credito'"},
                "numero_cuotas":  {"type": "integer", "description": "Cuotas si es crédito (default 1)"},
                "dias_primer_vencimiento": {"type": "integer", "description": "Días desde la fecha hasta la 1ª cuota (default 30)"},
                "dias_entre_cuotas": {"type": "integer", "description": "Días entre cuotas (default 30)"},
                "bodega":         {"type": "string", "description": f"Bodega de recepción (default '{BODEGA_DEFAULT}')"},
                "es_inventariable": {"type": "boolean", "description": "Default true"},
                "unidad_negocio": {"type": "string", "description": f"Default '{UNIDAD_NEGOCIO_DEFAULT}'"},
                "comprador":      {"type": "string", "description": "Nombre del comprador"},
                "observacion":    {"type": "string", "description": "Observación (máx. 6000 caracteres)"},
                "folio":          {"type": "integer", "description": "Folio manual (0 o vacío = automático)"},
                "giro":           {"type": "string"},
                "direccion":      {"type": "string"},
                "ciudad":         {"type": "string"},
                "comuna":         {"type": "string"},
                "confirmar":      {"type": "boolean", "description": "false = solo vista previa (default). true = enviar a Kame."},
            },
            "required": ["rut_proveedor", "razon_social", "comentario", "lineas"],
        },
    },
    {
        "name": "kame_cerrar_orden_compra",
        "description": (
            "Cierra manualmente una orden de compra aprobada (queda 'Cerrado Manual' y ya no admite recepciones). "
            "Requiere el ID interno de la OC, no el folio. Con confirmar=false (default) no envía nada; "
            "usar confirmar=true solo después de que el usuario lo apruebe."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_orden_compra": {"type": "integer", "description": "ID interno de la OC en Kame (no el folio)"},
                "observacion":     {"type": "string", "description": "Motivo del cierre (queda en el seguimiento)"},
                "confirmar":       {"type": "boolean", "description": "false = solo vista previa (default). true = cerrar en Kame."},
            },
            "required": ["id_orden_compra", "observacion"],
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

# ─── Órdenes de compra ────────────────────────────────────────────────────────
def _fecha_iso(texto: str = None) -> datetime:
    if not texto:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime.strptime(texto[:10], "%Y-%m-%d")

def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT00:00:00")

def construir_orden_compra(args: dict) -> dict:
    """Arma el cuerpo de addOrdenCompra a partir de datos simples, calculando montos."""
    if not KAME_USUARIO:
        raise ValueError("Falta configurar KAME_USUARIO (correo del usuario Kame) en claude_desktop_config.json")
    lineas = args.get("lineas") or []
    if not lineas:
        raise ValueError("La OC debe tener al menos una línea")
    comentario = (args.get("comentario") or "").strip()
    if not comentario:
        raise ValueError("El comentario (glosa) es obligatorio")
    if len(comentario) > 255:
        raise ValueError("El comentario no puede superar 255 caracteres")

    documento       = args.get("documento") or "Factura Electrónica"
    exenta          = "exenta" in documento.lower()
    compra_elect    = documento == "Factura de Compra Electrónica"
    inventariable   = args.get("es_inventariable", True)
    unidad_negocio  = args.get("unidad_negocio") or UNIDAD_NEGOCIO_DEFAULT
    fecha           = _fecha_iso(args.get("fecha"))
    fecha_recepcion = _fecha_iso(args.get("fecha_recepcion")) if args.get("fecha_recepcion") else fecha

    detalle, suma_lineas = [], 0
    for i, l in enumerate(lineas, 1):
        cantidad = float(l["cantidad"])
        precio   = float(l["precio_unitario"])
        pct      = float(l.get("porc_descuento") or 0)
        if cantidad <= 0 or precio < 0:
            raise ValueError(f"Línea {i}: cantidad debe ser > 0 y precio >= 0")
        tipo_art = l.get("tipo_articulo") or "ARTICULO"
        if inventariable and tipo_art == "ARTICULO" and not l.get("sku"):
            raise ValueError(f"Línea {i}: falta el SKU (obligatorio para artículos inventariables)")
        bruto     = round(cantidad * precio)
        total_lin = round(bruto * (1 - pct / 100))
        suma_lineas += total_lin
        item = {
            "Descripcion":          l["descripcion"],
            "DescripcionDetallada": (l.get("descripcion_detallada") or "")[:1024],
            "Cantidad":             cantidad,
            "UnidadNegocio":        unidad_negocio,
            "UnidadMedida":         l.get("unidad_medida") or "UN",
            "PrecioUnitario":       precio,
            "PorcDescuento":        pct,
            "Descuento":            bruto - total_lin,
            "Total":                total_lin,
            "TipoArticulo":         tipo_art,
        }
        if l.get("sku"):
            item["Articulo"] = l["sku"]
        detalle.append(item)

    afecto = 0 if exenta else suma_lineas
    exento = suma_lineas if exenta else 0
    iva    = 0 if exenta else round(afecto * TASA_IVA)
    total  = afecto + exento + iva

    body = {
        "Usuario":        KAME_USUARIO,
        "TipoDocumento":  "ORDENCOMPRA",
        "Documento":      documento,
        "Rut":            args["rut_proveedor"],
        "RznSocial":      args["razon_social"],
        "Fecha":          _iso(fecha),
        "Folio":          int(args.get("folio") or 0),
        "FechaRecepcion": _iso(fecha_recepcion),
        "Giro":           args.get("giro", ""),
        "Direccion":      args.get("direccion", ""),
        "Ciudad":         args.get("ciudad", ""),
        "Comuna":         args.get("comuna", ""),
        "Pais":           "Chile",
        "Comentario":     comentario,
        "TipoCompra":     "Del Giro",
        "Comprador":      args.get("comprador", ""),
        "Observacion":    (args.get("observacion") or "")[:6000],
        "EsInventariable": "S" if inventariable else "",
        "Detalle":        detalle,
        "Afecto":         afecto,
        "Exento":         exento,
        "Descuento":      0,
        "PorcDescuento":  0.0,
        "Recargo":        0,
        "PorcRecargo":    0.0,
        "TipoImpto1":     "IVA",
        "ValorImpto1":    iva,
        "IvaNoRecuperable": "No aplica",
        "total":          total,
    }
    if inventariable and any(d["TipoArticulo"] == "ARTICULO" for d in detalle):
        body["Bodega"] = args.get("bodega") or BODEGA_DEFAULT
    if compra_elect:
        body["TipoImpto2"]  = "IVA Retenido"
        body["ValorImpto2"] = iva

    if (args.get("forma_pago") or "credito") == "contado":
        body["FormaPago"] = "1"
        body["FechaVencimiento"] = _iso(fecha)
    else:
        n        = max(1, int(args.get("numero_cuotas") or 1))
        primer   = int(args.get("dias_primer_vencimiento") if args.get("dias_primer_vencimiento") is not None else 30)
        entre    = int(args.get("dias_entre_cuotas") or 30)
        base     = total // n
        cuotas   = []
        for k in range(n):
            monto = base if k < n - 1 else total - base * (n - 1)   # la última ajusta la diferencia
            cuotas.append({"FechaPago": _iso(fecha + timedelta(days=primer + k * entre)), "MontoPago": float(monto)})
        body["FormaPago"]        = "2"
        body["Cuotas"]           = cuotas
        body["FechaVencimiento"] = cuotas[-1]["FechaPago"]
    return body

def resumen_oc(body: dict) -> dict:
    return {
        "proveedor": f"{body['RznSocial']} ({body['Rut']})",
        "fecha":     body["Fecha"][:10],
        "lineas":    [f"{d['Cantidad']:g} x {d['Descripcion']} @ ${d['PrecioUnitario']:,.0f} = ${d['Total']:,.0f}"
                      for d in body["Detalle"]],
        "neto":      body["Afecto"] + body["Exento"],
        "iva":       body["ValorImpto1"],
        "total":     body["total"],
        "forma_pago": "Contado" if body["FormaPago"] == "1" else f"Crédito, {len(body['Cuotas'])} cuota(s)",
        "bodega":    body.get("Bodega", "(no inventariable)"),
    }

def oc_referenciadas(mes: int, anio: int) -> dict:
    """Agrupa el informe de compras por factura y extrae las referencias a OC."""
    desde, hasta = rango_mes(mes, anio)
    filas = GET_TODAS_LAS_PAGINAS("/Documento/getInformeCompras", {"fechaDesde": desde, "fechaHasta": hasta})

    facturas = {}
    for f in filas:
        clave = (f.get("Rut"), f.get("Documento"), f.get("Folio"))
        fac = facturas.setdefault(clave, {
            "proveedor": f.get("RznSocial"), "rut": f.get("Rut"),
            "documento": f.get("Documento"), "folio": f.get("Folio"),
            "fecha": (f.get("Fecha") or "")[:10], "comentario": f.get("Comentario"),
            "total": 0,
            "_ocs": {},
        })
        fac["total"] += f.get("Total") or 0   # el informe trae una fila por línea de detalle
        for n in (1, 2, 3):
            tipo  = str(f.get(f"NombreRef{n}") or "").strip()
            folio = str(f.get(f"FolioRef{n}") or "").strip()
            if folio and (tipo in CODIGOS_REF_OC or "orden de compra" in tipo.lower()):
                fac["_ocs"][folio] = (f.get(f"FechaRef{n}") or "")[:10]

    ordenes, sin_oc = {}, []
    for fac in facturas.values():
        ocs = fac.pop("_ocs")
        if not ocs:
            sin_oc.append(fac)
        for folio_oc, fecha_oc in ocs.items():
            o = ordenes.setdefault(folio_oc, {"folio_oc": folio_oc, "fecha_oc": fecha_oc,
                                              "proveedor": fac["proveedor"], "facturas": []})
            o["facturas"].append({"folio": fac["folio"], "fecha": fac["fecha"], "total": fac["total"]})

    return {
        "periodo": f"{mes:02d}/{anio}",
        "nota": "Solo incluye OC referenciadas en facturas de compra de este mes. "
                "Las OC aún sin factura no aparecen (la API de Kame no permite listarlas).",
        "ordenes_de_compra": sorted(ordenes.values(), key=lambda o: o["folio_oc"]),
        "facturas_sin_referencia_a_oc": sin_oc,
    }

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
            items = GET_TODAS_LAS_PAGINAS("/Documento/getInformeCompras", {
                "fechaDesde": desde, "fechaHasta": hasta,
            })
            data = {"items": items, "total_filas": len(items)}
        elif nombre == "kame_detalle_compra":
            tipo = requests.utils.quote(args["tipo_documento"])
            data = GET(f"/Documento/getCompra/{tipo}/{args['folio']}/{args['rut_proveedor']}")
        elif nombre == "kame_oc_referenciadas":
            data = oc_referenciadas(args["mes"], args["anio"])

        # ÓRDENES DE COMPRA
        elif nombre == "kame_crear_orden_compra":
            body = construir_orden_compra(args)
            if not args.get("confirmar"):
                data = {
                    "vista_previa": True,
                    "mensaje": "NO se ha enviado nada a Kame. Revisa los datos con el usuario y, "
                               "si los aprueba, vuelve a llamar con confirmar=true.",
                    "resumen": resumen_oc(body),
                    "json_a_enviar": body,
                }
            else:
                respuesta = POST("/Documento/addOrdenCompra", body)
                data = {"enviado": True, "resumen": resumen_oc(body), "respuesta_kame": respuesta}
        elif nombre == "kame_cerrar_orden_compra":
            if not KAME_USUARIO:
                raise ValueError("Falta configurar KAME_USUARIO en claude_desktop_config.json")
            id_oc = int(args["id_orden_compra"])
            if id_oc <= 0:
                raise ValueError("id_orden_compra debe ser mayor que 0")
            body = {"idOrdenCompra": id_oc, "observacion": args["observacion"], "usuario": KAME_USUARIO}
            if not args.get("confirmar"):
                data = {"vista_previa": True,
                        "mensaje": "NO se ha cerrado nada. Si el usuario lo aprueba, llama con confirmar=true.",
                        "json_a_enviar": body}
            else:
                data = {"enviado": True, "respuesta_kame": POST("/Documento/cerrarManualOrdenCompra", body)}

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
                "serverInfo": {"name": "kame-mcp", "version": "3.1.0"},
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
        es_error  = resultado.startswith('{"error"')
        send({
            "jsonrpc": "2.0", "id": mid,
            "result": {
                "content": [{"type": "text", "text": resultado}],
                "isError": es_error,
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
