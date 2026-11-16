import argparse
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QImageReader, QTransform
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QListWidgetItem
from .ui import WorkspaceUI
from .model import Measurement
from .storage import Store, find_images
from .viewer import ImageView


class MainWindow(WorkspaceUI, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Navico · Medición horizontal')
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.store = self.current = self.base_image = None
        self.paths = []
        self.viewer = ImageView()
        self.build_workspace()
        self.viewer.coordinates.connect(self.cursor_label.setText)
        self.viewer.hint.connect(self.hint_label.setText)
        self.viewer.mode_changed.connect(self.sync_tool)
        self.viewer.zoom_changed.connect(lambda scale: self.zoom_label.setText(f'{scale*100:.1f} %'))
        self.viewer.changed.connect(self.changed)
        self.enable_controls(False)

    def enable_controls(self, enabled):
        for widget in self.navigation_controls:
            widget.setEnabled(self.current is not None)
        for widget in self.edit_controls:
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
        self.distance_label.setText('— px')
        self.file_label.setText('Selecciona una imagen')
        self.dimensions_label.setText('—')
        self.zoom_label.setText('—')
        with QSignalBlocker(self.list):
            self.list.clear()
            for path in paths:
                relative = path.relative_to(store.root)
                item = QListWidgetItem(relative.as_posix())
                item.setData(Qt.ItemDataRole.UserRole, path.name)
                item.setData(Qt.ItemDataRole.UserRole + 1, relative.parent.as_posix() if relative.parent != Path('.') else store.root.name)
                item.setToolTip(str(path.resolve()))
                self.list.addItem(item)
        self.folder_label.setText(store.root.resolve().name)
        self.folder_label.setToolTip(str(store.root.resolve()))
        self.count_label.setText(f'{len(paths)} imagen' if len(paths) == 1 else f'{len(paths)} imágenes')
        self.save_label.setText('Solo lectura: configuración inválida' if store.blocked else 'Sin cambios pendientes')
        if paths:
            self.list.setCurrentRow(0)

    def select_image(self, row):
        self.current = self.base_image = None
        self.viewer.clear_image()
        self.enable_controls(False)
        self.distance_label.setText('— px')
        self.file_label.setText('Selecciona una imagen')
        self.dimensions_label.setText('—')
        self.zoom_label.setText('—')
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
        self.update_distance()
        if resized and not self.store.blocked:
            self.changed()

    def show_oriented(self):
        image = self.base_image.transformed(QTransform().rotate(self.current.rotation), Qt.TransformationMode.FastTransformation)
        self.viewer.load_image(image, self.current)
        path = self.paths[self.list.currentRow()]
        self.file_label.setText(path.name)
        self.file_label.setToolTip(str(path.resolve()))
        self.dimensions_label.setText(f'{image.width()} × {image.height()} px')

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
        self.distance_label.setText(f'{distance:g} px' if distance is not None else '— px')

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
