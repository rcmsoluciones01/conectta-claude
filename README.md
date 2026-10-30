# Conectta para Claude

Una skill de Claude para **conectar cualquier herramienta con Conectta**: un punto de venta, una tienda online, un CRM, un ERP o un sistema de pedidos. La instalas en tu Claude y Claude te guía y programa contigo cada pieza de la conexión, en tu lenguaje:

- **Recibir avisos** firmados de la cuenta de tu cliente: mensajes, conversaciones, ventas, citas, pedidos, etapas del Kanban y bajas.
- **Escribir a sus clientes por WhatsApp** con la clave de tu herramienta (texto o plantillas aprobadas).
- **Mandar pedidos** a Conectta, pagados o no: Conectta guarda el contacto y la conversación, y anota la venta solo si viene pagada.

Todo lo que explica está sacado del código de Conectta. Trae fragmentos listos para usar en **Node, Python y PHP**, y el ejemplo completo de **Luja**, la primera herramienta del catálogo.

Documentación pública de la API: <https://conectta.me/desarrolladores>.

## Instalación

### En Claude Code (plugin)

Dentro de Claude Code:

```
/plugin marketplace add https://github.com/rcmsoluciones01/conectta-claude.git
/plugin install conectta@conectta-claude
```

O desde la terminal:

```bash
claude plugin marketplace add https://github.com/rcmsoluciones01/conectta-claude.git
```

```bash
claude plugin install conectta@conectta-claude
```

Si tienes una llave SSH configurada en GitHub, también sirve la forma corta `rcmsoluciones01/conectta-claude`: clona por SSH y sin llave falla con «Permission denied (publickey)».

Para traer una versión nueva: `/plugin` → pestaña de marketplaces → `conectta-claude` → actualizar (o activar la actualización automática ahí mismo), y luego `/reload-plugins`.

### En claude.ai (archivo .zip)

1. Descarga [`conectar-con-conectta.zip`](https://github.com/rcmsoluciones01/conectta-claude/raw/main/dist/conectar-con-conectta.zip). No lo descomprimas.
2. En claude.ai, activa la ejecución de código: **Configuración → Capacidades → Ejecución de código y creación de archivos**.
3. Sube el .zip en la sección **Skills** (según la versión de la app está en **Personalizar → Skills → «+» → Subir una skill** o en **Configuración → Capacidades**).

Las skills de claude.ai son personales: cada persona del equipo sube su .zip.

## Cómo se usa

Se activa sola cuando hablas de conectar tu sistema con Conectta. También puedes llamarla en Claude Code con `/conectta:conectar-con-conectta`. Ejemplos:

- «Conecta mi tienda en Express con Conectta para recibir las ventas.»
- «Manda un pedido pagado desde mi sistema en Laravel a Conectta.»
- «Quiero avisar por WhatsApp al cliente cuando su pedido salga, desde mi ERP en Python.»
- «Mi receptor de avisos de Conectta dice que la firma no coincide.»
- «Integra Luja con Conectta de punta a punta.»

Para probar de verdad necesitas una cuenta de Conectta (sirve una de prueba) con WhatsApp conectado. Ahí, en **Ajustes → Herramientas conectadas**, conectas tu herramienta y copias el código `cnx_…` que te da.

¿Eres cliente de Conectta y quieres conectar Luja? Sigue la [guía paso a paso](docs/guia-conectar-luja.md).

## Qué hay dentro

```
plugins/conectta/skills/conectar-con-conectta/
├── SKILL.md                         el flujo de trabajo y las reglas
├── references/
│   ├── api.md                       código cnx_, autenticación, las 19 rutas, WhatsApp, pedidos, límites
│   ├── avisos.md                    los 14 avisos con su payload real
│   ├── verificacion-de-avisos.md    firma, reintentos, deduplicación, túnel
│   ├── errores.md                   cada error y qué hacer
│   ├── ejemplo-luja.md              la integración de Luja de punta a punta
│   └── huecos.md                    lo que hoy no se puede hacer y su rodeo
└── assets/
    ├── node/    conectta.mjs, servidor-avisos.mjs
    ├── python/  conectta.py, servidor_avisos.py
    └── php/     conectta.php, recibir-aviso.php
```

## Seguridad

El código `cnx_`, la clave y el secreto son de tu cliente: guárdalos como contraseñas (variables de entorno o un almacén cifrado), nunca en el repositorio ni en el navegador. Este repositorio no contiene ninguna clave real; todos los valores de los ejemplos son inventados.

## Licencia

[MIT](LICENSE): puedes usar, copiar y modificar este código, también en productos comerciales, siempre que conserves el aviso de copyright.

## Para quien mantiene este repositorio

- Validar: `claude plugin validate .` y `claude plugin validate ./plugins/conectta`.
- Rehacer el .zip tras cada cambio de la skill: `python scripts/empaquetar_zip.py`.
- Subir `version` en `plugins/conectta/.claude-plugin/plugin.json` en cada versión: quien tiene el plugin instalado solo recibe cambios cuando cambia.
- Si cambia la API de Conectta (rutas de la clave, avisos, firma o formato de pedidos), cambiar también `references/` y la página `/desarrolladores`.
