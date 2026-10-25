# Ofertas de juegos de Switch y Switch 2 — MediaMarkt España

Scraper en Python 3.10 o posterior, sin instalar paquetes. Descarga las categorías públicas de juegos, sigue la paginación y genera un informe HTML con buscador y filtros, JSON, CSV e historial SQLite.

## Web gratuita con actualización automática

La configuración de GitHub Pages y GitHub Actions está incluida en `.github/workflows/ofertas.yml`.
Consulta ambas categorías a las 00:17, 06:17, 12:17 y 18:17 UTC; en España peninsular son las 01:17, 07:17, 13:17 y 19:17 en invierno, una hora más en verano. GitHub puede retrasar las ejecuciones programadas.

Para crear el repositorio público y activar el despliegue en tu cuenta, instala Git y [GitHub CLI](https://cli.github.com/) y ejecuta desde esta carpeta:

```bash
python3 publicar.py
```

En Windows: `py publicar.py`. Si no has iniciado sesión, abrirá la autenticación oficial de GitHub. No pegues contraseñas ni tokens en el código o en un chat. El script crea `ofertas-switch`, sube los archivos, activa Pages con origen GitHub Actions y lanza la primera consulta. Si ese nombre ya existe y no pertenece a esta instalación, se detiene; puedes usar `--nombre ofertas-switch-mediamarkt`.

El script puede reanudarse desde la misma carpeta si se interrumpe después de crear el repositorio. Si tu sesión de GitHub CLI no permite subir workflows, ejecuta `gh auth refresh -s workflow` y vuelve a ejecutar el script. No requiere secretos personalizados en Actions: utiliza `GITHUB_TOKEN` con los permisos declarados.

La URL se muestra al terminar la configuración, pero solo estará disponible tras un workflow exitoso. Puedes ver el progreso en Actions → Actualizar ofertas y publicar web. También puedes iniciar una actualización con Run workflow.

El historial se conserva en `data/historial.sqlite`, dentro del repositorio público. La web solo recibe `index.html`, `productos.json` y `productos.csv`. Los cambios del historial no disparan otro workflow. Si el scraper se bloquea, obtiene una consulta parcial o no pasa las pruebas, se detiene el despliegue y se mantiene la última web publicada con su fecha original. Si es la primera ejecución, no se publicará ninguna web hasta obtener una consulta completa.

Los runners estándar de Actions y Pages son gratuitos para este repositorio público dentro de las condiciones y límites de GitHub. MediaMarkt podría bloquear las IP de los runners; en ese caso el workflow fallará sin intentar sortear el bloqueo. La ejecución en GitHub y la publicación deben comprobarse en el primer despliegue.

## Uso

Descomprime el ZIP, abre una terminal dentro de la carpeta y ejecuta:

```bash
python3 scraper.py
```

En Windows puedes usar `py scraper.py`. Después abre `resultados/ofertas.html` en el navegador. La primera ejecución completa puede tardar varios minutos: la tienda muestra pocos productos por página. El informe HTML es una instantánea; ejecutar el script vuelve a consultar la tienda.

Ejemplos:

```bash
# Descuentos o bajadas, hasta 40 euros y disponibles online
python3 scraper.py --solo-ofertas --precio-max 40 --solo-disponibles

# Solo Switch 2, descuentos calculados desde el 20 %
python3 scraper.py --consola switch2 --descuento-min 20

# Prueba corta de dos páginas por consola (resultado parcial)
python3 scraper.py --max-paginas 2
```

El historial usa la carpeta de salida. Conserva `resultados/historial.sqlite` para comparar ejecuciones; cambiar `--salida` inicia otro historial. Una oferta es un precio inferior al precio tachado publicado, o una bajada respecto a tu observación anterior. El mínimo observado solo cubre tus ejecuciones, no el historial completo de la tienda. Los descuentos se calculan con decimales y pueden diferir del porcentaje truncado que muestra MediaMarkt.

Por defecto el informe oculta los productos sin descuento ni bajada; desmarca «Solo descuentos o bajadas» para ver todos los descargados. Si has usado `--solo-ofertas`, los demás productos no se exportan. CSV almacena los importes en céntimos y utiliza `;` como separador. JSON indica fecha, avisos y total observado.

## Qué comprueba y qué límites tiene

- Utiliza las fichas del listado y sus precios, sin consultar APIs privadas ni automatizar compras.
- Consulta robots.txt, espera al menos 3 segundos entre páginas por defecto y respeta Crawl-delay cuando se publica. No sortea bloqueos ni CAPTCHA. Un error de red, un bloqueo o un cambio de estructura se comunica explícitamente.
- Marca el recorrido como parcial si se alcanza el límite de páginas, falla una categoría o se repiten resultados. Código de salida: 0 completo, 2 parcial con resultados, 1 error sin resultados utilizables. El máximo predeterminado es 200 páginas por consola y se puede cambiar.
- La disponibilidad online se confirma solo cuando el listado publica el estado AVAILABLE; las reservas o estados desconocidos quedan fuera de `--solo-disponibles`.
- La categoría determina la plataforma, con corrección a Switch 2 si lo indica el título. La taxonomía de la tienda puede contener productos mal clasificados.
- Identifica Game Key Card y códigos cuando el título lo especifica. «No especificado» no garantiza un cartucho completo. No consulta el contenido del cartucho ni el idioma de la edición.
- El vendedor se muestra solo cuando está identificado en la ficha. No asume que todos los productos los vende MediaMarkt: puede haber Marketplace. Compruébalo en la página del juego.
- Precio del juego sin portes, cupones, descuentos de carrito ni ventajas personalizadas. Los precios y el stock pueden cambiar después de consultar.
- Incluye programación automática mediante GitHub Actions; no incluye notificaciones propias. Para actualizar en local, ejecuta de nuevo el script. Evita ejecutar varias instancias sobre el mismo historial.

## Ejemplo incluido y validación

`ejemplo/ofertas.html` contiene la consulta real de muestra limitada a dos páginas por consola. Es un recorrido parcial, identificado como tal, y no representa todas las ofertas disponibles. Puedes abrirlo directamente sin Python. La extracción se ha contrastado también con las primeras páginas reales de ambas categorías.

Pruebas del parser de precios, aislamiento del precio reacondicionado, disponibilidad, paginación y comparación histórica:

```bash
python3 -m unittest -v
```

Las páginas pueden cambiar; si dejan de reconocerse fichas, habrá que actualizar los selectores `data-test` de `parse()`.
