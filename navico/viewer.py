from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPen, QPixmap, QPainter
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from .model import pixel_at, make_roi


class ImageView(QGraphicsView):
    changed = Signal()
    coordinates = Signal(str)
    zoom_changed = Signal(float)
    hint = Signal(str)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor('#242830'))
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.record = None
        self.mode = None
        self.first = None
        self.hover = None
        self.overlays = []
        self.pixmap = None
        self.space = False
        self.drag_pos = None

    def load_image(self, image, record):
        self.cancel()
        self.scene().clear()
        self.overlays = []
        self.record = record
        self.pixmap = self.scene().addPixmap(QPixmap.fromImage(image))
        self.scene().setSceneRect(0, 0, image.width(), image.height())
        self.redraw()
        self.fit_image()

    def clear_image(self):
        self.cancel()
        self.scene().clear()
        self.overlays = []
        self.record = self.pixmap = None
        self.coordinates.emit('X: —   Y: —')

    def fit_image(self):
        if self.pixmap:
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.zoom_changed.emit(self.transform().m11())

    def set_zoom(self, value):
        if self.pixmap:
            value = max(.01, min(64, value))
            self.scale(value / self.transform().m11(), value / self.transform().m11())
            self.zoom_changed.emit(value)

    def wheelEvent(self, event):
        self.set_zoom(self.transform().m11() * (1.25 if event.angleDelta().y() > 0 else .8))
        event.accept()

    def set_mode(self, mode):
        self.cancel()
        self.mode = mode
        self.setFocus()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.hint.emit('Selecciona dos puntos. Escape cancela; espacio + arrastre desplaza.')

    def cancel(self):
        self.mode = self.first = self.hover = None
        self.space = False
        self.drag_pos = None
        self.unsetCursor()
        if self.record:
            self.redraw()

    def point_at(self, position):
        if not self.pixmap:
            return None
        pos = self.mapToScene(position)
        return pixel_at(pos.x(), pos.y(), self.pixmap.pixmap().width(), self.pixmap.pixmap().height())

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None:
            delta = event.position().toPoint() - self.drag_pos
            self.drag_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        self.hover = self.point_at(event.position().toPoint())
        self.coordinates.emit(f'X: {self.hover[0]}   Y: {self.hover[1]}' if self.hover else 'X: —   Y: —')
        if self.first:
            self.redraw()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.coordinates.emit('X: —   Y: —')
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.pixmap and (event.button() == Qt.MouseButton.MiddleButton or (self.space and event.button() == Qt.MouseButton.LeftButton)):
            self.drag_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        point = self.point_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and self.mode and point:
            if self.first is None:
                self.first = self.hover = point
            else:
                if self.mode == 'line':
                    ys = sorted((self.first[1], point[1]))
                    geometry = (self.first[0], *ys) if ys[0] != ys[1] else None
                else:
                    geometry = make_roi(self.first, point)
                if geometry is None:
                    self.hint.emit('Elige un segundo punto que defina un elemento de tamaño mayor que cero.')
                    return
                setattr(self.record, self.mode, geometry)
                self.cancel()
                self.changed.emit()
            self.redraw()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_pos is not None:
            self.drag_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.space else Qt.CursorShape.CrossCursor if self.mode else Qt.CursorShape.ArrowCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            self.hint.emit('Dibujo cancelado.')
        elif event.key() == Qt.Key.Key_Space:
            self.space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space = False
            self.drag_pos = None
            self.setCursor(Qt.CursorShape.CrossCursor if self.mode else Qt.CursorShape.ArrowCursor)
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self.space = False
        self.drag_pos = None
        super().focusOutEvent(event)

    def redraw(self):
        for item in self.overlays:
            self.scene().removeItem(item)
        self.overlays = []
        if not self.record:
            return
        def pen(color, width, dashed=False):
            p = QPen(QColor(color), width)
            p.setCapStyle(Qt.PenCapStyle.FlatCap)
            if dashed:
                p.setStyle(Qt.PenStyle.DashLine)
            return p
        def line(g, p):
            x, a, b = g
            self.overlays.append(self.scene().addLine(x + .5, a + .5, x + .5, b + .5, p))
        def roi(g, p):
            a, b, c, d = g
            self.overlays.append(self.scene().addRect(a + .5, b + .5, c-a, d-b, p))
        r = self.record
        if r.line:
            line(r.line, pen('#ff5252', r.line_width))
        if r.roi:
            roi(r.roi, pen('#00d98b', r.roi_width))
        if self.first and self.hover:
            if self.mode == 'line':
                line((self.first[0], *sorted((self.first[1], self.hover[1]))), pen('#ffe066', r.line_width, True))
            elif self.mode == 'roi':
                g = make_roi(self.first, self.hover)
                if g:
                    roi(g, pen('#ffe066', r.roi_width, True))
        if r.distance is not None:
            x, a, b = r.line
            y = (a + b) / 2 + .5
            center = (r.roi[0] + r.roi[2]) / 2 + .5
            self.overlays.append(self.scene().addLine(x+.5, y, center, y, pen('#0070ff', 1, True)))
            text = self.scene().addSimpleText(f'Distancia: {r.distance:g} px')
            text.setBrush(QColor('#0066ff'))
            font = text.font()
            font.setPixelSize(16)
            font.setBold(True)
            text.setFont(font)
            text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            text.setPos(8, 8)
            self.overlays.append(text)
