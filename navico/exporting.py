"""Exportación por lotes sin acceso a widgets ni modificaciones del origen."""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import tempfile

from PySide6.QtCore import Qt, QThread, Signal, QSaveFile, QIODevice
from PySide6.QtGui import QImageReader, QTransform
from .rendering import annotated_image


@dataclass
class ExportReport:
    destination: Path
    exported: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    cancelled: bool = False


def complete_measurements(root, paths, items):
    result = []
    for path in paths:
        relative = path.relative_to(root)
        record = items.get(relative.as_posix())
        if record is not None and record.distance is not None:
            result.append((relative, deepcopy(record)))
    return result


def create_destination(root, selected):
    root, selected = Path(root).resolve(), Path(selected).resolve()
    if selected == root or selected.is_relative_to(root):
        raise ValueError('Elige una carpeta de destino fuera de la carpeta de imágenes de origen.')
    if not selected.is_dir():
        raise ValueError('La carpeta de destino no existe.')
    prefix = f'navico-resultados-{datetime.now().astimezone():%Y%m%d-%H%M%S}-'
    return Path(tempfile.mkdtemp(prefix=prefix, dir=selected))


def export_image(source, target, record):
    reader = QImageReader(str(source))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise OSError(f'No se pudo leer la imagen: {reader.errorString()}')
    if (image.width(), image.height()) != record.size:
        raise ValueError('Las dimensiones cambiaron; vuelve a configurar la medición.')
    image = image.transformed(QTransform().rotate(record.rotation), Qt.TransformationMode.FastTransformation)
    rendered = annotated_image(image, record)
    target.parent.mkdir(parents=True, exist_ok=True)
    file = QSaveFile(str(target))
    file.setDirectWriteFallback(False)
    if not file.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(file.errorString())
    try:
        if not rendered.save(file, 'PNG'):
            raise OSError(f'No se pudo escribir el PNG: {file.errorString()}')
        if not file.commit():
            raise OSError(f'No se pudo completar el PNG: {file.errorString()}')
    except Exception:
        file.cancelWriting()
        raise


def export_batch(root, destination, entries, cancelled=lambda: False, progress=lambda *args: None):
    report = ExportReport(Path(destination))
    for number, (relative, record) in enumerate(entries):
        if cancelled():
            report.cancelled = True
            break
        progress(number, len(entries), relative.as_posix())
        try:
            target = destination / relative.parent / (relative.name + '.png')
            export_image(root / relative, target, record)
            report.exported.append(relative.as_posix())
        except Exception as exc:
            report.errors.append((relative.as_posix(), str(exc)))
        progress(number+1, len(entries), relative.as_posix())
    return report


class ExportWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, root, destination, entries, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.destination = Path(destination)
        self.entries = entries
        self.report = ExportReport(self.destination)

    def run(self):
        try:
            self.report = export_batch(self.root, self.destination, self.entries,
                                       self.isInterruptionRequested, self.progress.emit)
        except Exception as exc:
            self.report.errors.append(('Exportación', str(exc)))
