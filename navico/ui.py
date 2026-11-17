"""Componentes y estilo del espacio de trabajo de escritorio."""
from PySide6.QtCore import Qt, QSize, QRectF, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QSplitter, QSpinBox, QDoubleSpinBox, QFrame, QScrollArea, QSizePolicy,
    QStyledItemDelegate, QStyle)

ACCENT = '#0066ff'
TEXT = '#172333'
MUTED = '#637083'
BORDER = '#dce2ea'
CANVAS = '#242830'
STYLE = f'''
QMainWindow, QWidget#workspace {{ background: #ffffff; }}
QWidget {{ color: {TEXT}; font-size: 13px; }}
QWidget#header, QWidget#sidebar, QWidget#inspector, QWidget#viewToolbar {{ background: #ffffff; }}
QWidget#header {{ border-bottom: 1px solid {BORDER}; }}
QWidget#viewToolbar {{ border-bottom: 1px solid {BORDER}; }}
QLabel#brand {{ color: #1556b8; font-size: 25px; font-weight: 700; }}
QLabel#sectionTitle {{ font-size: 19px; font-weight: 700; }}
QLabel#groupTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#fileTitle {{ font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#distance {{ color: {ACCENT}; font-size: 34px; font-weight: 700; }}
QLabel#distanceMm {{ color: {ACCENT}; font-size: 26px; font-weight: 700; }}
QLabel#zoomValue {{ background: #f5f7fa; border: 1px solid {BORDER}; border-radius: 5px; padding: 6px 0; }}
QPushButton {{ background: #ffffff; border: 1px solid #cdd5e0; border-radius: 6px;
    min-height: 32px; padding: 0 10px; }}
QPushButton:hover {{ background: #f1f6fd; border-color: #97b9ee; }}
QPushButton:pressed {{ background: #dceaff; }}
QPushButton:focus {{ border: 2px solid {ACCENT}; }}
QPushButton:checked {{ background: #eaf2ff; color: {ACCENT}; border: 1px solid {ACCENT}; }}
QPushButton[primary="true"] {{ background: {ACCENT}; color: #ffffff; border-color: {ACCENT}; font-weight: 600; }}
QPushButton[primary="true"]:hover {{ background: #0055d4; }}
QPushButton[quiet="true"] {{ background: #f5f7fa; }}
QPushButton:disabled {{ color: #9aa4b2; background: #f5f7fa; border-color: #e4e8ee; }}
QSpinBox, QDoubleSpinBox {{ background: #ffffff; border: 1px solid #cdd5e0; border-radius: 5px;
    min-height: 32px; padding-left: 10px; }}
QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: #9aa4b2; background: #f5f7fa; }}
QListWidget {{ border: none; background: #ffffff; outline: none; }}
QScrollArea {{ border: none; background: #ffffff; }}
QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{ background: #f5f7fa; border-top: 1px solid {BORDER}; min-height: 32px; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ padding: 0 8px; font-size: 12px; }}
QToolTip {{ color: {TEXT}; background: #ffffff; border: 1px solid {BORDER}; padding: 5px; }}
'''


def icon(kind, color=TEXT):
    """Pequeños iconos vectoriales pintados por Qt; sin fuentes ni assets externos."""
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(2, 2)
    p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == 'folder':
        p.drawPolyline(QPolygonF([QPointF(2, 16), QPointF(2, 4), QPointF(8, 4), QPointF(10, 6), QPointF(18, 6), QPointF(18, 16), QPointF(2, 16)]))
    elif kind == 'image':
        p.drawRoundedRect(QRectF(2, 3, 16, 14), 1, 1)
        p.drawEllipse(QRectF(5, 6, 2, 2))
        p.drawPolyline(QPolygonF([QPointF(3, 15), QPointF(8, 10), QPointF(11, 13), QPointF(14, 9), QPointF(18, 14)]))
    elif kind in ('left', 'right'):
        if kind == 'right':
            p.translate(20, 0)
            p.scale(-1, 1)
        p.drawArc(QRectF(4, 5, 12, 12), -70*16, 280*16)
        p.drawPolyline(QPolygonF([QPointF(4, 3), QPointF(4, 8), QPointF(9, 8)]))
    elif kind == 'line':
        p.drawLine(10, 2, 10, 18)
    elif kind == 'roi':
        p.drawRect(QRectF(2, 4, 16, 12))
    elif kind in ('plus', 'minus'):
        p.drawLine(4, 10, 16, 10)
        if kind == 'plus':
            p.drawLine(10, 4, 10, 16)
    p.end()
    result = QIcon()
    result.addPixmap(pixmap)
    return result


class ElidedLabel(QLabel):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self.full_text = ''
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self.full_text = text
        self.setToolTip(text)
        self.refresh()

    def refresh(self):
        super().setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, max(0, self.contentsRect().width())))

    def resizeEvent(self, event):
        self.refresh()
        super().resizeEvent(event)


class ImageListDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(200, 64)

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.fillRect(rect, QColor('#e8f1ff' if selected else '#f5f8fc' if hovered else '#ffffff'))
        if selected:
            painter.fillRect(rect.x(), rect.y(), 3, rect.height(), QColor(ACCENT))
        icon('image', ACCENT if selected else MUTED).paint(painter, rect.x()+16, rect.y()+20, 20, 20)
        text_rect = rect.adjusted(48, 10, -12, -10)
        font = option.font
        font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        name = index.data(Qt.ItemDataRole.UserRole)
        painter.drawText(text_rect.x(), rect.y()+26, painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, text_rect.width()))
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor(MUTED))
        folder = index.data(Qt.ItemDataRole.UserRole + 1)
        painter.drawText(text_rect.x(), rect.y()+46, painter.fontMetrics().elidedText(folder, Qt.TextElideMode.ElideRight, text_rect.width()))
        painter.setPen(QColor('#edf0f4'))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.restore()


def rule(vertical=False):
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.VLine if vertical else QFrame.Shape.HLine)
    frame.setStyleSheet(f'color: {BORDER};')
    return frame


def title(text, name='sectionTitle'):
    label = QLabel(text)
    label.setObjectName(name)
    return label


class WorkspaceUI:
    """Construye los paneles; el controlador conserva la lógica de imágenes."""
    def build_workspace(self):
        self.setStyleSheet(STYLE)
        self.navigation_controls = []
        self.edit_controls = []
        self.draw_buttons = {}
        self.widths = {}
        root = QWidget()
        root.setObjectName('workspace')
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.build_header())
        self.splitter = QSplitter()
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.build_sidebar())
        self.splitter.addWidget(self.build_center())
        self.splitter.addWidget(self.build_inspector())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([280, 908, 250])
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(root)
        self.build_status()

    def build_header(self):
        header = QWidget()
        header.setObjectName('header')
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(24)
        brand = title('Machining Network', 'brand')
        brand.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.addWidget(brand)
        self.file_label = ElidedLabel('Selecciona una imagen')
        self.file_label.setObjectName('fileTitle')
        layout.addWidget(self.file_label, 1)
        self.dimensions_label = title('—', 'muted')
        layout.addWidget(self.dimensions_label)
        return header

    def build_sidebar(self):
        side = QWidget()
        side.setObjectName('sidebar')
        side.setMinimumWidth(220)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QVBoxLayout()
        top.setContentsMargins(16, 20, 16, 16)
        top.setSpacing(12)
        top.addWidget(title('Imágenes'))
        open_button = QPushButton('Abrir carpeta…')
        open_button.setIcon(icon('folder', '#ffffff'))
        open_button.setProperty('primary', True)
        open_button.clicked.connect(self.choose_folder)
        top.addWidget(open_button)
        self.export_button = QPushButton('Guardar Imagenes')
        self.export_button.setToolTip('Exportar todas las mediciones completas como PNG')
        self.export_button.clicked.connect(self.choose_export_destination)
        self.export_button.setEnabled(False)
        top.addWidget(self.export_button)
        self.folder_label = ElidedLabel('Sin carpeta')
        self.folder_label.setObjectName('fileTitle')
        top.addWidget(self.folder_label)
        self.count_label = title('0 imágenes', 'muted')
        top.addWidget(self.count_label)
        layout.addLayout(top)
        layout.addWidget(rule())
        self.list = QListWidget()
        self.list.setItemDelegate(ImageListDelegate(self.list))
        self.list.setMouseTracking(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.currentRowChanged.connect(self.select_image)
        layout.addWidget(self.list, 1)
        return side

    def control(self, text, callback, group, kind=None, tooltip=None):
        button = QPushButton(text)
        if kind:
            button.setIcon(icon(kind))
        if tooltip:
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
        button.clicked.connect(callback)
        group.append(button)
        return button

    def build_center(self):
        center = QWidget()
        center.setMinimumWidth(500)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar = QWidget()
        toolbar.setObjectName('viewToolbar')
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(12, 12, 12, 12)
        bar.setSpacing(6)
        bar.addWidget(title('Rotar:', 'muted'))
        self.rotate_left = self.control('−90°', lambda: self.rotate(-90), self.edit_controls, 'left', 'Girar 90° a la izquierda')
        self.rotate_right = self.control('+90°', lambda: self.rotate(90), self.edit_controls, 'right', 'Girar 90° a la derecha')
        bar.addWidget(self.rotate_left)
        bar.addWidget(self.rotate_right)
        bar.addWidget(rule(True))
        bar.addWidget(title('Zoom:', 'muted'))
        for kind, multiplier in [('minus', .8), ('plus', 1.25)]:
            b = self.control('', lambda checked=False, m=multiplier: self.viewer.set_zoom(self.viewer.transform().m11()*m), self.navigation_controls,
                             kind, 'Reducir zoom' if kind == 'minus' else 'Ampliar zoom')
            b.setFixedWidth(32)
            bar.addWidget(b)
            if kind == 'minus':
                self.zoom_label = QLabel('—')
                self.zoom_label.setObjectName('zoomValue')
                self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.zoom_label.setFixedWidth(56)
                bar.addWidget(self.zoom_label)
        bar.addWidget(self.control('100 %', lambda: self.viewer.set_zoom(1), self.navigation_controls))
        bar.addWidget(self.control('Ajustar', self.viewer.fit_image, self.navigation_controls))
        bar.addStretch()
        layout.addWidget(toolbar)
        self.viewer.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.viewer, 1)
        return center

    def build_inspector(self):
        scroll = QScrollArea()
        scroll.setMinimumWidth(230)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QWidget()
        panel.setObjectName('inspector')
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        layout.addWidget(title('Medición'))
        layout.addWidget(rule())
        layout.addWidget(QLabel('Distancia horizontal'))
        self.distance_label = title('— px', 'distance')
        layout.addWidget(self.distance_label)
        self.distance_mm_label = title('— mm', 'distanceMm')
        self.distance_mm_label.setAccessibleName('Distancia en milímetros')
        layout.addWidget(self.distance_mm_label)
        layout.addWidget(rule())
        layout.addWidget(title('Tamaño de referencia', 'groupTitle'))
        note = title('Ancho equivalente a 7 mm', 'muted')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.reference_spin = QDoubleSpinBox()
        self.reference_spin.setDecimals(3)
        self.reference_spin.setRange(0, 1_000_000_000_000)
        self.reference_spin.setSuffix(' px')
        self.reference_spin.setSpecialValueText('Sin referencia')
        self.reference_spin.setKeyboardTracking(False)
        self.reference_spin.setAccessibleName('Tamaño de referencia en píxeles para 7 mm')
        self.reference_spin.valueChanged.connect(self.set_reference)
        self.edit_controls.append(self.reference_spin)
        layout.addWidget(self.reference_spin)
        reference_button = self.control('Medir referencia', lambda: self.viewer.set_mode('reference'), self.edit_controls)
        reference_button.setToolTip('Dos puntos: se mide la longitud en cualquier dirección')
        reference_button.setCheckable(True)
        self.draw_buttons['reference'] = reference_button
        layout.addWidget(reference_button)
        layout.addWidget(rule())
        for key, heading, color, draw_text, erase_text in [
                ('line', 'Línea vertical', '#ff5252', 'Dibujar línea', 'Borrar línea'),
                ('roi', 'ROI rectangular', '#00b877', 'Dibujar ROI', 'Borrar ROI')]:
            layout.addWidget(title(heading, 'groupTitle'))
            draw_row = QHBoxLayout()
            swatch = QLabel()
            swatch.setPixmap(icon(key, color).pixmap(24, 24))
            swatch.setFixedWidth(28)
            draw_row.addWidget(swatch)
            draw = self.control(draw_text, lambda checked=False, k=key: self.viewer.set_mode(k), self.edit_controls)
            draw.setCheckable(True)
            self.draw_buttons[key] = draw
            draw_row.addWidget(draw, 1)
            layout.addLayout(draw_row)
            width_row = QHBoxLayout()
            width_label = QLabel('Grosor:')
            width_row.addWidget(width_label)
            width_row.addStretch()
            spin = QSpinBox()
            spin.setRange(1, 50)
            spin.setValue(2)
            spin.setSuffix(' px')
            spin.setFixedWidth(100)
            spin.setAccessibleName(f'Grosor de {heading.lower()}')
            width_label.setBuddy(spin)
            spin.valueChanged.connect(lambda value, k=key+'_width': self.set_width(k, value))
            self.widths[key+'_width'] = spin
            self.edit_controls.append(spin)
            width_row.addWidget(spin)
            layout.addLayout(width_row)
            erase = self.control(erase_text, lambda checked=False, k=key: self.erase(k), self.edit_controls)
            erase.setProperty('quiet', True)
            layout.addWidget(erase)
            layout.addWidget(rule())
        self.hint_label = title('Selecciona una herramienta para dibujar.', 'muted')
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)
        layout.addStretch()
        scroll.setWidget(panel)
        return scroll

    def build_status(self):
        self.save_label = QLabel('Sin carpeta')
        self.save_label.setMinimumWidth(230)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addWidget(self.save_label)
        self.status_help = QLabel('Rueda: zoom · Espacio + arrastre: desplazar')
        self.status_help.setObjectName('muted')
        self.status_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.statusBar().addWidget(self.status_help, 1)
        self.cursor_label = QLabel('X: —   Y: —')
        self.cursor_label.setMinimumWidth(140)
        self.cursor_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addPermanentWidget(self.cursor_label)

    def sync_tool(self, mode):
        for key, button in self.draw_buttons.items():
            button.setChecked(key == mode)
        self.hint_label.setText('Selecciona dos puntos.\nEscape para cancelar.' if mode else 'Selecciona una herramienta para dibujar.')
