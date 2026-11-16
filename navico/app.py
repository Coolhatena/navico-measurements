import argparse
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QImageReader, QTransform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QSplitter, QFileDialog, QMessageBox, QSpinBox)
from .model import Measurement
from .storage import Store, find_images
from .viewer import ImageView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Navico · Medición horizontal')
        self.resize(1280, 850)
        self.store = self.current = self.base_image = None
        self.paths = []
        self.viewer = ImageView()
        self.list = QListWidget()
        self.list.setMinimumWidth(230)
        self.list.currentRowChanged.connect(self.select_image)
        self.folder_label = QLabel('Abre una carpeta para comenzar')
        self.folder_label.setWordWrap(True)
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.addWidget(self.folder_label)
        sl.addWidget(self.list)
        splitter = QSplitter()
        splitter.addWidget(side)
        splitter.addWidget(self.viewer)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 980])
        root = QWidget()
        layout = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        def button(label, callback, target=toolbar):
            b = QPushButton(label)
            b.clicked.connect(callback)
            target.addWidget(b)
            return b
        button('Abrir carpeta…', self.choose_folder)
        self.image_controls = []
        for label, callback in [('↶ 90°', lambda: self.rotate(-90)), ('↷ 90°', lambda: self.rotate(90)),
                                ('−', lambda: self.viewer.set_zoom(self.viewer.transform().m11() / 1.25)),
                                ('+', lambda: self.viewer.set_zoom(self.viewer.transform().m11() * 1.25)),
                                ('100 %', lambda: self.viewer.set_zoom(1)), ('Ajustar', self.viewer.fit_image)]:
            self.image_controls.append(button(label, callback))
        self.zoom_label = QLabel('100 %')
        toolbar.addWidget(self.zoom_label)
        toolbar.addStretch()
        tools = QHBoxLayout()
        layout.addLayout(tools)
        for label, callback in [('Dibujar línea', lambda: self.viewer.set_mode('line')), ('Dibujar ROI', lambda: self.viewer.set_mode('roi')),
                                ('Borrar línea', lambda: self.erase('line')), ('Borrar ROI', lambda: self.erase('roi'))]:
            self.image_controls.append(button(label, callback, tools))
        self.widths = {}
        for key, label in [('line_width', 'Grosor línea:'), ('roi_width', 'Grosor ROI:')]:
            tools.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(1, 50)
            spin.setValue(2)
            spin.setSuffix(' px')
            spin.valueChanged.connect(lambda value, k=key: self.set_width(k, value))
            tools.addWidget(spin)
            self.widths[key] = spin
            self.image_controls.append(spin)
        self.distance_label = QLabel('Distancia: —')
        self.distance_label.setStyleSheet('color: #0066ff; font-weight: bold; font-size: 18px;')
        layout.addWidget(self.distance_label)
        layout.addWidget(splitter, 1)
        self.hint_label = QLabel('Dos clics para dibujar · Escape cancela · Rueda: zoom · Espacio + arrastre: desplazar')
        layout.addWidget(self.hint_label)
        self.setCentralWidget(root)
        self.cursor_label = QLabel('X: —   Y: —')
        self.statusBar().addPermanentWidget(self.cursor_label)
        self.save_label = QLabel('Sin carpeta')
        self.statusBar().addWidget(self.save_label)
        self.viewer.coordinates.connect(self.cursor_label.setText)
        self.viewer.hint.connect(self.hint_label.setText)
        self.viewer.zoom_changed.connect(lambda scale: self.zoom_label.setText(f'{scale*100:.1f} %'))
        self.viewer.changed.connect(self.changed)
        self.enable_controls(False)

    def enable_controls(self, enabled):
        for widget in self.image_controls:
            widget.setEnabled(enabled)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Seleccionar carpeta con imágenes')
        if folder:
            self.open_folder(folder)

    def flush(self):
        if not self.store or not self.store.dirty:
            return True
        try:
            self.store.save()
            self.save_label.setText('Guardado automáticamente')
            return True
        except OSError as exc:
            self.save_label.setText('Cambios pendientes · error de guardado')
            QMessageBox.warning(self, 'No se pudo guardar', str(exc))
            return False

    def allow_leave(self):
        if self.flush():
            return True
        return QMessageBox.question(self, 'Cambios sin guardar', 'Hay cambios que no se pudieron guardar. ¿Descartarlos y continuar?',
                                    QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                    QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Discard

    def open_folder(self, folder):
        if not Path(folder).is_dir():
            QMessageBox.warning(self, 'Carpeta inválida', f'No existe la carpeta: {folder}')
            return
        if not self.allow_leave():
            return
        store = Store(folder)
        try:
            paths = find_images(store.root)
        except OSError as exc:
            QMessageBox.warning(self, 'No se pudo leer la carpeta', str(exc))
            return
        try:
            store.load()
        except ValueError as exc:
            QMessageBox.warning(self, 'Configuración inválida', f'{exc}\n\nSe abrirá en modo de solo lectura. Respalda o corrige el archivo y vuelve a abrir la carpeta.')
        self.store = store
        self.paths = paths
        self.current = self.base_image = None
        self.viewer.clear_image()
        self.enable_controls(False)
        self.distance_label.setText('Distancia: —')
        with QSignalBlocker(self.list):
            self.list.clear()
            self.list.addItems([p.relative_to(store.root).as_posix() for p in paths])
        self.folder_label.setText(f'{store.root}\n{len(paths)} imágenes')
        self.save_label.setText('Solo lectura: configuración inválida' if store.blocked else 'Sin cambios pendientes')
        if paths:
            self.list.setCurrentRow(0)

    def select_image(self, row):
        self.viewer.clear_image()
        self.current = self.base_image = None
        self.enable_controls(False)
        self.distance_label.setText('Distancia: —')
        if row < 0 or row >= len(self.paths):
            return
        path = self.paths[row]
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            QMessageBox.warning(self, 'Imagen ilegible', f'{path.name}\n{reader.errorString()}')
            return
        key = path.relative_to(self.store.root).as_posix()
        record = self.store.items.setdefault(key, Measurement())
        size = (image.width(), image.height())
        resized = record.size is not None and record.size != size
        if resized:
            record.line = record.roi = None
            QMessageBox.warning(self, 'Dimensiones modificadas', 'La imagen cambió de dimensiones. Se eliminaron sus dibujos para evitar mediciones incorrectas.')
        record.size = size
        self.current = record
        self.base_image = image
        for key, spin in self.widths.items():
            with QSignalBlocker(spin):
                spin.setValue(getattr(record, key))
        self.show_oriented()
        self.enable_controls(not self.store.blocked)
        # El zoom y ajuste siguen disponibles en modo de solo lectura.
        if self.store.blocked:
            for widget in self.image_controls[2:6]:
                widget.setEnabled(True)
        self.update_distance()
        if resized and not self.store.blocked:
            self.changed()

    def show_oriented(self):
        image = self.base_image.transformed(QTransform().rotate(self.current.rotation), Qt.TransformationMode.FastTransformation)
        self.viewer.load_image(image, self.current)

    def rotate(self, degrees):
        if not self.current:
            return
        if self.current.line or self.current.roi:
            answer = QMessageBox.question(self, 'Girar imagen', 'Al girar se borrarán la línea y el ROI. ¿Continuar?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.current.line = self.current.roi = None
        self.current.rotation = (self.current.rotation + degrees) % 360
        self.show_oriented()
        self.changed()

    def erase(self, key):
        if self.current:
            self.viewer.cancel()
            setattr(self.current, key, None)
            self.changed()

    def set_width(self, key, value):
        if self.current:
            setattr(self.current, key, value)
            self.changed()

    def update_distance(self):
        distance = self.current.distance if self.current else None
        self.distance_label.setText(f'Distancia: {distance:g} px' if distance is not None else 'Distancia: —')

    def changed(self):
        self.viewer.redraw()
        self.update_distance()
        self.store.dirty = True
        self.flush()

    def closeEvent(self, event):
        if self.allow_leave():
            event.accept()
        else:
            event.ignore()


def main():
    parser = argparse.ArgumentParser(description='Medición horizontal de imágenes')
    parser.add_argument('folder', nargs='?', type=Path, help='Carpeta de imágenes opcional')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Navico Measurements')
    window = MainWindow()
    window.show()
    if args.folder:
        window.open_folder(args.folder)
    sys.exit(app.exec())
