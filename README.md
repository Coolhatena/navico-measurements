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
5. Consulta la distancia en el panel derecho y en azul sobre la imagen. La línea punteada es horizontal a la altura del punto medio de la línea vertical. En la barra inferior aparecen el estado de guardado y las coordenadas del cursor.

La rueda y los botones **+ / −** cambian el zoom (hasta 6400 %); **100 %** restablece la escala y **Ajustar** encaja la imagen en la ventana. Para mover la imagen usa **espacio + arrastre** o el botón central. El visor debe tener el foco para los atajos. **Escape** cancela un dibujo pendiente sin borrar el anterior. La barra inferior muestra las coordenadas del cursor dentro de la imagen; fuera muestra guiones.

Los clics seleccionan centros de píxel, numerados desde `(0, 0)` en la esquina superior izquierda de la imagen orientada. A gran aumento no se suavizan los píxeles. Los grosores independientes van de 1 a 50 píxeles de imagen y crecen simétricamente: no cambian el centro ni la medición.

La distancia es `abs((x_izquierda_ROI + x_derecha_ROI) / 2 - x_línea)` en píxeles originales, sin dependencia de las posiciones Y o del zoom. Un ROI puede tener centro de medio píxel; se muestra sin redondear a entero. Los puntos del ROI son centros de píxel de sus bordes, no los bordes exteriores del trazo. No hay conversión a unidades físicas.

## Guardado

Cada cambio completo se guarda automáticamente en `.navico-measurements.json` dentro de la carpeta abierta. Los originales nunca se modifican. Conserva este archivo junto con las imágenes para recuperar rotaciones, dibujos y grosores; las rutas son relativas y permiten mover la carpeta completa.

Abre siempre la misma carpeta raíz para recuperar sus mediciones. Abrir directamente una subcarpeta utiliza su propio archivo de configuración. Renombrar o mover una imagen dentro de la carpeta cambia su identidad. Si cambian las dimensiones, los dibujos se invalidan con un aviso; reemplazar una imagen por otra de iguales dimensiones no se detecta.

El guardado utiliza reemplazo atómico. Un fallo de escritura deja los cambios pendientes en memoria; cerrar o cambiar de carpeta exige reintentar o descartar explícitamente. Si el JSON es inválido, la carpeta se abre en modo de solo lectura: respalda o corrige el archivo y vuelve a abrirla. No se sobrescribe automáticamente.

Se admiten imágenes estáticas; en TIFF de varias páginas se muestra la primera. No incluye exportación de imágenes anotadas ni CSV.

## Pruebas

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v
```

Las pruebas cubren geometría, validación, guardado atómico, errores de escritura, selección con zoom, desplazamiento, cancelación, rotación, reapertura y protección de originales. No necesitan modificar las imágenes de ejemplo.
