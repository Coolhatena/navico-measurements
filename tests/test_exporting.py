import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QRectF, QBuffer, QIODevice, QSaveFile, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QTransform, QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from navico.model import Measurement
from navico.rendering import annotated_image, distance_text_layout
from navico.exporting import (export_image, export_batch, complete_measurements,
                              create_destination, ExportWorker)
from navico.viewer import ImageView
from navico.app import MainWindow


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'origen'
        self.root.mkdir()
        self.destination = Path(self.temp.name) / 'destino'
        self.destination.mkdir()
        self.image = QImage(300, 200, QImage.Format.Format_ARGB32)
        self.image.fill(QColor('white'))
        self.source = self.root / 'foto.png'
        self.image.save(str(self.source))
        self.record = Measurement(size=(300, 200), line=(40, 50, 170), roi=(100, 60, 181, 140), line_width=5, roi_width=3)

    def test_scene_and_png_are_identical_at_every_rotation(self):
        view = ImageView()
        self.addCleanup(view.close)
        self.record.reference_width_px = 49
        for rotation in (0, 90, 180, 270):
            self.record.rotation = rotation
            target = self.destination / f'{rotation}.png'
            export_image(self.source, target, self.record)
            oriented = self.image.transformed(QTransform().rotate(rotation), Qt.TransformationMode.FastTransformation)
            view.load_image(oriented, self.record)
            view.set_zoom(8)
            # Una previsualización no pertenece al PNG exportado.
            view.set_mode('roi')
            view.first, view.hover = (1, 1), (20, 20)
            view.redraw()
            export_image(self.source, target, self.record)
            view.cancel()
            actual = QImage(str(target)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            expected = QImage(oriented.size(), QImage.Format.Format_ARGB32_Premultiplied)
            expected.fill(Qt.GlobalColor.transparent)
            painter = QPainter(expected)
            rect = QRectF(0, 0, oriented.width(), oriented.height())
            view.scene().render(painter, rect, rect)
            painter.end()
            self.assertEqual(actual, expected)
            self.assertEqual(actual.size(), oriented.size())
            self.assertEqual(actual.pixelColor(40, 60), QColor('#ff5252'))
            self.assertEqual(actual.pixelColor(100, 80), QColor('#00d98b'))

    def test_text_scales_with_zoom_and_uses_image_coordinates(self):
        view = ImageView()
        self.addCleanup(view.close)
        view.resize(1000, 800)
        view.show()
        view.load_image(self.image, self.record)
        self.app.processEvents()
        item = view.overlays[0]
        distances = []
        for zoom in (.5, 1, 2, 4):
            view.set_zoom(zoom)
            transform = item.deviceTransform(view.viewportTransform())
            a, b = transform.map(QPointF(8, 8)), transform.map(QPointF(8, 24))
            distances.append(b.y()-a.y())
        self.assertEqual(distances, [8, 16, 32, 64])
        result = annotated_image(self.image, self.record)
        blue = [result.pixelColor(x, y).blue() > 200 and result.pixelColor(x, y).red() < 80
                for y in range(8, 30) for x in range(8, 200)]
        self.assertTrue(any(blue))

    def test_complete_snapshot_nested_names_and_originals(self):
        paths, items, originals = [], {}, {}
        for folder in ('CAPA A', 'CAPA B'):
            path = self.root / folder / 'igual.jpg'
            path.parent.mkdir()
            self.image.save(str(path))
            paths.append(path)
            items[path.relative_to(self.root).as_posix()] = self.record
            originals[path] = path.read_bytes()
        paths.append(self.source)
        items['foto.png'] = Measurement(size=(300, 200), line=(10, 1, 20))
        entries = complete_measurements(self.root, paths, items)
        self.assertEqual(len(entries), 2)
        self.record.line_width = 50
        self.assertEqual(entries[0][1].line_width, 5)
        report = export_batch(self.root, self.destination, entries)
        self.assertEqual(len(report.exported), 2)
        self.assertFalse(report.errors)
        for path in paths[:2]:
            self.assertEqual(path.read_bytes(), originals[path])
            self.assertTrue((self.destination / path.relative_to(self.root).parent / 'igual.jpg.png').is_file())
        self.assertFalse((self.destination / 'foto.png.png').exists())

    def test_adaptive_text_reference_sizes_and_rotation(self):
        for width, height, expected in [(1200, 1600, 64), (2400, 3200, 128), (600, 800, 32)]:
            for w, h in [(width, height), (height, width)]:
                font, origin, scale = distance_text_layout('Distancia: 525.5 px', QRectF(0, 0, w, h))
                self.assertEqual(font.pixelSize(), expected)
                self.assertEqual(scale, 1)
                self.assertTrue(font.bold())

    def test_adaptive_text_fits_small_and_unusual_images(self):
        text = 'Distancia: 123456789.5 px'
        for width, height in [(32, 24), (16, 1200), (1200, 16), (240, 1800), (6000, 160), (1, 1)]:
            bounds = QRectF(0, 0, width, height)
            font, origin, scale = distance_text_layout(text, bounds)
            metrics = QFontMetricsF(font)
            box = metrics.boundingRect(text).united(QRectF(0, -metrics.ascent(), metrics.horizontalAdvance(text), metrics.height()))
            transform = QTransform().translate(origin.x(), origin.y()).scale(scale, scale)
            actual = transform.mapRect(box)
            margin = min(width, height)*.01
            self.assertAlmostEqual(actual.left(), margin)
            self.assertAlmostEqual(actual.top(), margin)
            self.assertLessEqual(actual.right(), width-margin+1e-6)
            self.assertLessEqual(actual.bottom(), height-margin+1e-6)

    def test_continue_after_read_dimension_and_write_errors(self):
        (self.root / 'roto.png').write_bytes(b'invalido')
        changed = Measurement(size=(400, 200), line=(40, 50, 170), roi=(100, 60, 181, 140))
        entries = [(Path('roto.png'), self.record), (Path('foto.png'), changed), (Path('foto.png'), self.record)]
        report = export_batch(self.root, self.destination, entries)
        self.assertEqual(report.exported, ['foto.png'])
        self.assertEqual(len(report.errors), 2)
        with patch('navico.exporting.export_image', side_effect=[OSError('Sin permiso'), None]):
            report = export_batch(self.root, self.destination, entries[:2])
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(len(report.exported), 1)

    def test_cancel_between_images_and_empty_batch(self):
        count = []
        entries = [(Path('foto.png'), self.record), (Path('otra.png'), self.record)]
        report = export_batch(self.root, self.destination, entries, cancelled=lambda: bool(count),
                              progress=lambda done, total, name: count.append(done) if done == 1 else None)
        self.assertTrue(report.cancelled)
        self.assertEqual(report.exported, ['foto.png'])
        self.assertTrue((self.destination / 'foto.png.png').exists())
        self.assertFalse((self.destination / 'otra.png.png').exists())
        empty = export_batch(self.root, self.destination, [])
        self.assertFalse(empty.exported or empty.errors or empty.cancelled)

    def test_atomic_png_commit_failure_retains_previous_file(self):
        class FailedCommit(QSaveFile):
            def commit(self):
                return False
        target = self.destination / 'foto.png'
        target.write_bytes(b'anterior')
        with patch('navico.exporting.QSaveFile', FailedCommit):
            with self.assertRaises(OSError):
                export_image(self.source, target, self.record)
        self.assertEqual(target.read_bytes(), b'anterior')
        self.assertEqual(list(self.destination.iterdir()), [target])

    def test_destination_is_unique_and_outside_source_including_symlinks(self):
        with self.assertRaises(ValueError):
            create_destination(self.root, self.root)
        inside = self.root / 'dentro'
        inside.mkdir()
        with self.assertRaises(ValueError):
            create_destination(self.root, inside)
        link = self.destination / 'enlace'
        link.symlink_to(inside, target_is_directory=True)
        with self.assertRaises(ValueError):
            create_destination(self.root, link)
        self.assertNotEqual(create_destination(self.root, self.destination), create_destination(self.root, self.destination))

    def test_exif_orientation_before_user_rotation(self):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.image.save(buffer, 'JPEG')
        jpeg = bytes(buffer.data())
        exif = b'Exif\0\0II' + struct.pack('<HIH', 42, 8, 1)
        exif += struct.pack('<HHIHHI', 0x112, 3, 1, 6, 0, 0)
        source = self.root / 'exif.jpg'
        source.write_bytes(jpeg[:2] + b'\xff\xe1' + struct.pack('>H', len(exif)+2) + exif + jpeg[2:])
        self.record.size = (200, 300)
        self.record.rotation = 90
        target = self.destination / 'exif.png'
        export_image(source, target, self.record)
        self.assertEqual(QImage(str(target)).size().toTuple(), (300, 200))

    def test_worker_renders_in_background(self):
        worker = ExportWorker(self.root, self.destination, [(Path('foto.png'), self.record)])
        worker.start()
        self.assertTrue(worker.wait(10000))
        self.assertEqual(worker.report.exported, ['foto.png'])
        self.assertFalse(worker.report.errors)

    def test_ui_export_pending_changes_and_restores_controls(self):
        w = MainWindow()
        w.show()
        self.addCleanup(w.close)
        w.open_folder(self.root)
        self.assertFalse(w.export_button.isEnabled())
        w.current.line, w.current.roi = self.record.line, self.record.roi
        # Configuración pendiente en memoria: no se requiere un JSON guardado.
        w.store.dirty = True
        w.update_export_button()
        self.assertTrue(w.export_button.isEnabled())
        failures = []
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok), patch.object(sys, 'excepthook', side_effect=lambda *args: failures.append(args)):
            w.start_export(self.destination)
            worker = w.export_worker
            self.assertFalse(w.centralWidget().isEnabled())
            deadline = time.monotonic()+10
            while w.export_worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(5)
        self.assertIsNone(w.export_worker)
        self.assertTrue(w.centralWidget().isEnabled())
        self.assertTrue(w.draw_buttons['line'].isEnabled())
        self.assertEqual(worker.report.exported, ['foto.png'])
        self.assertFalse((self.root / '.navico-measurements.json').exists())
        self.assertFalse(failures)

    def test_ui_close_cancels_and_waits_for_current_image(self):
        w = MainWindow()
        w.show()
        self.addCleanup(w.close)
        self.image.save(str(self.root / 'otra.png'))
        w.open_folder(self.root)
        for path in w.paths:
            w.store.items[path.relative_to(self.root).as_posix()] = Measurement.from_dict(self.record.to_dict())
        started, release = threading.Event(), threading.Event()
        original_export = export_image
        def delayed(*args):
            started.set()
            release.wait(5)
            return original_export(*args)
        failures = []
        with patch('navico.exporting.export_image', side_effect=delayed), patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok), patch.object(sys, 'excepthook', side_effect=lambda *args: failures.append(args)):
            w.start_export(self.destination)
            worker = w.export_worker
            self.assertTrue(started.wait(2))
            self.assertFalse(w.close())
            self.assertTrue(worker.isInterruptionRequested())
            release.set()
            deadline = time.monotonic()+10
            while w.export_worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(5)
        self.assertIsNone(w.export_worker)
        self.assertTrue(worker.report.cancelled)
        self.assertEqual(len(worker.report.exported), 1)
        self.assertFalse(worker.report.errors)
        self.assertTrue(w.centralWidget().isEnabled())
        self.assertFalse(failures)


if __name__ == '__main__':
    unittest.main()
