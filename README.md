# Navico · Medición horizontal

Aplicación de escritorio en Python y PySide6, con interfaz en español. No requiere servidor ni conexión a internet después de instalar las dependencias.

## Instalación y ejecución

Requiere Python 3.10 o posterior compatible con PySide6 6.12. En macOS, las dependencias fijadas requieren macOS 14 o posterior. Validado con Python 3.14.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

También puedes abrir directamente una carpeta:

```sh
.venv/bin/python main.py images
```

En Windows: activa con `.venv\Scripts\activate` y usa `python main.py`.

## Uso

La ventana se organiza en tres columnas ajustables: **Imágenes** a la izquierda, el **visor** en el centro y **Medición** a la derecha. Sobre el visor están los giros y el zoom. El panel derecho agrupa el resultado, el dibujo y el grosor de cada elemento; la herramienta activa se resalta en azul. Los nombres largos se abrevian y su ruta completa aparece al dejar el cursor encima. El inspector permite desplazarse verticalmente en ventanas pequeñas. La ventana mínima es de 1100 × 700.

1. Abre una carpeta. El listado izquierdo incluye imágenes JPG/JPEG, PNG, BMP y TIFF de todas sus subcarpetas, ordenadas por ruta. Selecciona con el ratón o las flechas del teclado.
2. Orienta la imagen con los botones de giro de 90°. Si hay dibujos, se solicita confirmación antes de borrarlos. Primero se respeta la orientación EXIF de la fotografía.
3. Pulsa **Dibujar línea** y haz dos clics. La X del primero fija la línea vertical; el segundo fija su otro extremo en Y.
4. Pulsa **Dibujar ROI** y elige dos esquinas opuestas en cualquier orden. Cada imagen tiene una línea y un ROI; dibujar otro reemplaza el anterior al completar los dos puntos.
5. Configura el **Tamaño de referencia**: escribe cuántos píxeles corresponden a una longitud de **7 mm**, o pulsa **Medir referencia** y elige dos puntos en cualquier dirección. Se calcula la longitud real `hypot(x2 − x1, y2 − y1)`, admitiendo líneas horizontales, verticales y diagonales; por ejemplo, 30 px en X y 40 px en Y equivalen a 50 px. El resultado se carga en el campo y se guarda con tres decimales. La línea es temporal y desaparece al completar; Escape cancela sin cambiar el valor anterior. Solo se rechazan dos puntos coincidentes. La distancia entre la línea de medición y el centro del ROI sigue calculándose en X.
6. Consulta las distancias en píxeles y milímetros en el panel derecho y en azul sobre la imagen. La línea punteada es horizontal a la altura del punto medio de la línea vertical. En la barra inferior aparecen el estado de guardado y las coordenadas del cursor.

La rueda y los botones **+ / −** cambian el zoom (hasta 6400 %); **100 %** restablece la escala y **Ajustar** encaja la imagen en la ventana. Para mover la imagen usa **espacio + arrastre** o el botón central. El visor debe tener el foco para los atajos. **Escape** cancela un dibujo pendiente sin borrar el anterior. La barra inferior muestra las coordenadas del cursor dentro de la imagen; fuera muestra guiones.

Los clics seleccionan centros de píxel, numerados desde `(0, 0)` en la esquina superior izquierda de la imagen orientada. A gran aumento no se suavizan los píxeles. Los grosores independientes van de 1 a 50 píxeles de imagen y crecen simétricamente: no cambian el centro ni la medición.

El texto azul de distancia muestra dos líneas: `DISTANCIA: 14px` y, debajo, `DISTANCIA MM: 2mm`. Forma parte de las anotaciones de la imagen y adapta automáticamente su tamaño al lado menor: `64 × lado_menor / 1200`, redondeado a píxeles. Por ejemplo, usa 64 px en imágenes de 1200 × 1600, 128 px en 2400 × 3200 y 32 px en 600 × 800. Se dibuja en negrita arriba a la izquierda, con un margen del 1 % del lado menor. Si el bloque completo no cabe, su tamaño se reduce para evitar recortes. Tanto el texto como las marcas aumentan y disminuyen con el zoom; el visor y los PNG exportados utilizan el mismo cálculo. Los resultados del panel derecho mantienen su tamaño para poder consultarlos con cualquier aumento.

La distancia es `abs((x_izquierda_ROI + x_derecha_ROI) / 2 - x_línea)` en píxeles originales, sin dependencia de las posiciones Y o del zoom. Un ROI puede tener centro de medio píxel; se muestra sin redondear a entero. Los puntos del ROI son centros de píxel de sus bordes, no los bordes exteriores del trazo.

La referencia admite hasta tres decimales y se guarda por imagen. La escala es `referencia_px / 7` píxeles por milímetro y la conversión es `distancia_mm = distancia_px × 7 / referencia_px`. Por ejemplo, con una referencia de 49 px, una distancia de 14 px equivale a 2 mm. El cálculo conserva la precisión y el resultado en milímetros se muestra con hasta dos decimales, sin ceros finales. Esta conversión supone una escala uniforme en la imagen.

Un valor de cero en el campo significa **Sin referencia** y elimina la calibración. Sin referencia se conserva el resultado en píxeles y se muestra `DISTANCIA MM: —`. Sin línea o ROI completos, ambos resultados del panel quedan pendientes. La referencia numérica se conserva al girar y borrar dibujos; la línea temporal de referencia no se guarda ni exporta.

## Guardado

Cada cambio completo se guarda automáticamente en `.navico-measurements.json` dentro de la carpeta abierta. Los originales nunca se modifican. Conserva este archivo junto con las imágenes para recuperar rotaciones, dibujos, grosores y referencia numérica; las rutas son relativas y permiten mover la carpeta completa. Las configuraciones anteriores sin `reference_width_px` se abren sin referencia y conservan sus dibujos.

Abre siempre la misma carpeta raíz para recuperar sus mediciones. Abrir directamente una subcarpeta utiliza su propio archivo de configuración. Renombrar o mover una imagen dentro de la carpeta cambia su identidad. Si cambian las dimensiones, los dibujos y la referencia se invalidan con un aviso; reemplazar una imagen por otra de iguales dimensiones no se detecta.

El guardado utiliza reemplazo atómico. Un fallo de escritura deja los cambios pendientes en memoria; cerrar o cambiar de carpeta exige reintentar o descartar explícitamente. Si el JSON es inválido, la carpeta se abre en modo de solo lectura: respalda o corrige el archivo y vuelve a abrirla. No se sobrescribe automáticamente.

Se admiten imágenes estáticas; en TIFF de varias páginas se muestra la primera. No incluye exportación CSV.

## Exportar imágenes anotadas

Pulsa **Guardar Imagenes**, debajo de **Abrir carpeta…**. El botón se habilita cuando al menos una imagen de la carpeta abierta tiene línea y ROI completos. Exporta todas las mediciones completas encontradas, incluidas las configuraciones actuales en memoria que todavía no se hayan podido guardar en el JSON. Las imágenes incompletas y los dibujos de previsualización no se exportan. El botón se deshabilita si la configuración es inválida.

Selecciona una carpeta fuera de la carpeta de origen. Se creará dentro de ella una subcarpeta única `navico-resultados-<fecha-hora>-<identificador>`, conservando las subcarpetas de las imágenes. Cada archivo conserva su nombre original y añade `.png`: por ejemplo, `CAPA A/foto.jpeg.png`. Así se distinguen imágenes con igual nombre base y diferentes extensiones, y cada exportación tiene su propia carpeta.

Los PNG se guardan sin pérdida, a resolución original y con la orientación EXIF y los giros configurados ya aplicados. Incluyen la línea vertical, el ROI, sus grosores, la línea punteada y las dos líneas de distancia. Una imagen con línea y ROI completos sigue siendo exportable sin referencia: su segunda línea indica `DISTANCIA MM: —`. El zoom, la selección actual y el área visible no afectan al resultado. El visor y la exportación comparten el mismo renderizador de anotaciones. Los archivos originales y el JSON no se modifican al exportar.

La exportación se ejecuta en segundo plano con progreso; la edición y el cambio de carpeta se bloquean mientras dure. **Cancelar** termina primero la imagen actual y conserva las imágenes ya exportadas. Si intentas cerrar la ventana durante la exportación, se solicita la cancelación; puedes cerrarla cuando aparezca el resumen. Un archivo ilegible, un error de escritura o unas dimensiones diferentes de las guardadas se registran como fallo y el lote continúa. Al final se muestran el destino, el número de resultados, los pendientes y los detalles de archivos exportados y errores. Cada PNG se guarda de forma atómica para evitar resultados parcialmente escritos.

## Pruebas

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v
```

Las pruebas cubren geometría, validación, guardado atómico, errores de escritura, selección con zoom, desplazamiento, cancelación, rotación, reapertura y protección de originales. También verifican la referencia manual y por dos puntos, conversión a milímetros, compatibilidad con configuraciones anteriores, texto multilínea, igualdad entre el renderizado del visor y el PNG, escalado del texto, orientación EXIF, exportación por lotes, errores parciales y cancelación en segundo plano. No necesitan modificar las imágenes de ejemplo.
