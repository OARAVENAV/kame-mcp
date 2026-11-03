# Kame MCP — Ferretería Bismarck SpA

Servidor MCP que conecta Claude con la API de Kame ERP (api.kameone.cl) para consultar ventas, compras, stock, cobros, pagos y contabilidad, y para crear y cerrar órdenes de compra.

## Herramientas disponibles

| Área | Herramienta | Descripción |
|---|---|---|
| Ventas | `kame_informe_ventas` | Informe mensual de ventas (facturas, boletas, guías) |
| | `kame_detalle_venta` | Detalle de una venta por tipo de documento y folio |
| Cotizaciones | `kame_informe_cotizaciones` | Cotizaciones del mes |
| | `kame_detalle_cotizacion` | Detalle de una cotización |
| Pedidos | `kame_detalle_pedido` | Detalle de un pedido |
| Compras | `kame_informe_compras` | Facturas de compra del mes (todas las páginas) |
| | `kame_detalle_compra` | Detalle de una factura de compra |
| | `kame_oc_referenciadas` | OC referenciadas en las facturas de compra del mes |
| Órdenes de compra | `kame_crear_orden_compra` | Crea una OC (calcula IVA, totales y cuotas) |
| | `kame_cerrar_orden_compra` | Cierra manualmente una OC aprobada |
| Inventario | `kame_stock_general`, `kame_stock_articulo`, `kame_stock_bodega`, `kame_stock_articulo_bodega` | Stock |
| Cobros | `kame_cuentas_por_cobrar`, `kame_informe_cobros` | Deudores y cobros |
| Pagos | `kame_cuentas_por_pagar`, `kame_informe_pagos` | Proveedores y pagos |
| Maestros | `kame_lista_articulos`, `kame_lista_clientes`, `kame_lista_vendedores`, `kame_lista_precios_venta`, `kame_lista_precios_compra` | Catálogos |
| Contabilidad | `kame_libro_diario` | Libro diario del mes |

### Sobre las órdenes de compra

- **La API de Kame no permite listar OC.** `kame_oc_referenciadas` las reconstruye a partir de las facturas de compra que las referencian. Las OC que todavía no tienen factura no aparecen.
- **Crear y cerrar son operaciones que escriben en Kame.** Por defecto (`confirmar=false`) solo devuelven una vista previa con los montos calculados. Claude debe mostrarte esa vista previa y enviar con `confirmar=true` únicamente después de que la apruebes.
- `kame_cerrar_orden_compra` pide el **ID interno** de la OC, no el folio.

## Instalación

1. Instala la dependencia:
   ```
   pip install requests
   ```

2. Configura Claude Desktop (`claude_desktop_config.json`):
   - Copia el contenido de `claude_desktop_config.json` de este repo
   - Pégalo en: `C:\Users\TuUsuario\AppData\Roaming\Claude\claude_desktop_config.json`
   - Ajusta la ruta a `server.py` y completa tus datos **en tu computador**

3. Reinicia Claude Desktop

### Variables de configuración

| Variable | Obligatoria | Descripción |
|---|---|---|
| `KAME_CLIENT_ID` / `KAME_CLIENT_SECRET` | Sí | Kame → Datos de empresa → Cliente ID / Cliente Secret |
| `KAME_USUARIO` | Para crear/cerrar OC | Correo del usuario Kame con el que se registran las OC |
| `KAME_BODEGA_DEFAULT` | No | Bodega por defecto de las OC (default `Bismarck`) |
| `KAME_UNIDAD_NEGOCIO_DEFAULT` | No | Unidad de negocio por defecto (default `Casa Matriz`) |

> ⚠️ **Nunca subas credenciales reales a este repositorio** (es público). Complétalas solo en el `claude_desktop_config.json` de tu computador.

## Uso con Claude

- "¿Cuáles fueron las ventas de octubre 2026?"
- "¿Qué órdenes de compra se facturaron en noviembre?"
- "Crea una OC a Servimetal por 20 perfiles 40x30x2 a $9.432"
- "Cierra la OC con ID 12345 porque el proveedor no tiene stock"
