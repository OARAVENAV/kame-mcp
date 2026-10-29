# Kame MCP — Ferretería Bismarck SpA

Servidor MCP que conecta Claude con la API de Kame ERP para consultas de ventas, stock e informes.

## Herramientas disponibles

| Herramienta | Descripción |
|---|---|
| `kame_informe_ventas` | Informe mensual de ventas (facturas, boletas, guías) |
| `kame_stock` | Stock disponible por artículo o bodega |
| `kame_cuentas_por_cobrar` | Reporte de deudores |
| `kame_cuentas_por_pagar` | Reporte de proveedores |
| `kame_lista_articulos` | Catálogo de productos |
| `kame_lista_clientes` | Listado de clientes (fichas) |
| `kame_detalle_venta` | Detalle de una venta específica |

## Instalación

1. Instala la dependencia:
   ```
   pip install requests
   ```

2. Crea un archivo `.env` con tus credenciales (copia `.env.ejemplo`):
   ```
   KAME_CLIENT_ID=tu_client_id
   KAME_CLIENT_SECRET=tu_client_secret
   ```

3. Configura Claude Desktop (`claude_desktop_config.json`):
   - Copia el contenido de `claude_desktop_config.json`
   - Pégalo en: `C:\Users\TuUsuario\AppData\Roaming\Claude\claude_desktop_config.json`
   - Ajusta la ruta a `server.py` y tus credenciales

4. Reinicia Claude Desktop

## Uso con Claude

Una vez conectado, puedes preguntarle a Claude:
- "¿Cuáles fueron las ventas de octubre 2025?"
- "¿Cuánto stock tenemos de planchas de acero?"
- "Muéstrame las cuentas por cobrar"
- "Lista todos los clientes registrados"
