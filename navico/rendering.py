"""Anotaciones en píxeles de imagen, compartidas por el visor y los PNG."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QFont, QFontMetricsF, QPainter, QImage
from PySide6.QtWidgets import QGraphicsItem
from .model import format_mm


def annotation_pen(color, width, dashed=False):
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    return pen


def draw_line(painter, geometry, pen):
    x, a, b = geometry
    painter.setPen(pen)
    painter.drawLine(QPointF(x+.5, a+.5), QPointF(x+.5, b+.5))


def draw_roi(painter, geometry, pen):
    a, b, c, d = geometry
    painter.setPen(pen)
    painter.drawRect(QRectF(a+.5, b+.5, c-a, d-b))


def distance_caption(record):
    if record.distance is None:
        return ''
    mm = f'{format_mm(record.distance_mm)}mm' if record.distance_mm is not None else '—'
    return f'DISTANCIA: {record.distance:g}px\nDISTANCIA MM: {mm}'


def distance_text_bounds(text, font):
    metrics = QFontMetricsF(font)
    result = None
    for index, line in enumerate(text.split('\n')):
        rect = metrics.boundingRect(line).united(QRectF(
            0, -metrics.ascent(), metrics.horizontalAdvance(line), metrics.height()))
        rect.translate(0, index*metrics.lineSpacing())
        result = rect if result is None else result.united(rect)
    return result


def distance_text_layout(text, bounds):
    """Fuente, posición de línea base y escala; medidas en píxeles de imagen."""
    side = min(bounds.width(), bounds.height())
    margin = side * .01
    available_width = bounds.width() - 2*margin
    available_height = bounds.height() - 2*margin
    size = max(1, round(64*side/1200))
    font = QFont()
    font.setBold(True)
    while True:
        font.setPixelSize(size)
        rect = distance_text_bounds(text, font)
        fit = min(1., available_width/max(rect.width(), 1), available_height/max(rect.height(), 1))
        if fit >= 1 or size == 1:
            break
        size = max(1, min(size-1, int(size*fit)))
    # Incluso una imagen diminuta puede requerir menos de un píxel de fuente.
    origin = QPointF(bounds.left()+margin-rect.left()*fit,
                     bounds.top()+margin-rect.top()*fit)
    return font, origin, fit


def draw_annotations(painter, record, bounds):
    painter.save()
    try:
        painter.setClipRect(bounds, Qt.ClipOperation.IntersectClip)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if record.line:
            draw_line(painter, record.line, annotation_pen('#ff5252', record.line_width))
        if record.roi:
            draw_roi(painter, record.roi, annotation_pen('#00d98b', record.roi_width))
        if record.distance is not None:
            x, a, b = record.line
            y = (a+b)/2+.5
            center = (record.roi[0]+record.roi[2])/2+.5
            painter.setPen(annotation_pen('#0070ff', 1, True))
            painter.drawLine(QPointF(x+.5, y), QPointF(center, y))
            text = distance_caption(record)
            font, origin, scale = distance_text_layout(text, bounds)
            painter.setFont(font)
            painter.setPen(QColor('#0066ff'))
            painter.translate(origin)
            painter.scale(scale, scale)
            spacing = QFontMetricsF(font).lineSpacing()
            for index, line in enumerate(text.split('\n')):
                painter.drawText(QPointF(0, index*spacing), line)
    finally:
        painter.restore()


class AnnotationItem(QGraphicsItem):
    def __init__(self, record, bounds):
        super().__init__()
        self.record = record
        self.bounds = QRectF(bounds)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return self.bounds

    def paint(self, painter, option, widget=None):
        draw_annotations(painter, self.record, self.bounds)


def annotated_image(image, record):
    result = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if result.isNull():
        raise OSError('No hay memoria suficiente para renderizar la imagen')
    painter = QPainter(result)
    try:
        draw_annotations(painter, record, QRectF(0, 0, result.width(), result.height()))
    finally:
        painter.end()
    return result
