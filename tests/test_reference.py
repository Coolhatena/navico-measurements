import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QPointF, QPoint, QRectF
from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from navico.model import Measurement, format_mm
from navico.storage import Store
from navico.rendering import distance_caption, distance_text_layout, distance_text_bounds
from navico.exporting import export_image, complete_measurements
from navico.app import MainWindow


class ReferenceModelTests(unittest.TestCase):
    def test_conversion_and_formatting(self):
        r = Measurement(line=(10, 30, 100), roi=(20, 40, 28, 60), reference_width_px=49)
        self.assertEqual(r.distance, 14)
        self.assertEqual(r.distance_mm, 2)
        self.assertEqual(distance_caption(r), 'DISTANCIA: 14px\nDISTANCIA MM: 2mm')
        r.reference_width_px = 24.5
        self.assertEqual(r.distance_mm, 4)
        r.reference_width_px = 51.234
        self.assertAlmostEqual(r.distance_mm, 14*7/51.234)
        self.assertEqual(format_mm(r.distance_mm), '1.91')
        r.line = (24, 30, 100)
        self.assertEqual(r.distance_mm, 0)
        self.assertEqual(format_mm(r.distance_mm), '0')
        r.reference_width_px = None
        self.assertIsNone(r.distance_mm)
        self.assertTrue(distance_caption(r).endswith('DISTANCIA MM: —'))
        r.line = None
        self.assertIsNone(r.distance_mm)
        self.assertEqual(distance_caption(r), '')

    def test_reference_validation_and_legacy_configuration(self):
        record = Measurement(size=(200, 160), reference_width_px=49.125)
        self.assertEqual(Measurement.from_dict(record.to_dict()), record)
        for invalid in (True, False, 0, -1, float('nan'), float('inf'), '49', [], 10**1000):
            data = record.to_dict()
            data['reference_width_px'] = invalid
            with self.assertRaises(ValueError):
                Measurement.from_dict(data)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            data = record.to_dict()
            del data['reference_width_px']
            store.path.write_text(json.dumps({'version': 1, 'images': {'foto.png': data}}))
            store.load()
            self.assertIsNone(store.items['foto.png'].reference_width_px)
            store.items['foto.png'].reference_width_px = 49.125
            store.save()
            loaded = Store(tmp)
            loaded.load()
            self.assertEqual(loaded.items['foto.png'].reference_width_px, 49.125)


class ReferenceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = QImage(200, 160, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        image.save(str(self.root / 'a.png'))
        image.save(str(self.root / 'b.png'))
        self.window = MainWindow()
        self.window.show()
        self.window.open_folder(self.root)
        self.addCleanup(self.window.close)
        self.app.processEvents()
        self.window.current.line = (10, 30, 100)
        self.window.current.roi = (20, 40, 28, 60)
        self.window.changed()

    def click_pixel(self, x, y):
        view = self.window.viewer
        pos = view.mapFromScene(QPointF(x+.5, y+.5))
        candidates = [pos + QPoint(dx, dy) for dx in (0, -1, 1) for dy in (0, -1, 1)]
        pos = next(p for p in candidates if view.point_at(p) == (x, y))
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)

    def test_manual_value_persists_per_image_and_clears_to_none(self):
        w = self.window
        w.reference_spin.setValue(49)
        self.assertEqual(w.distance_label.text(), '14 px')
        self.assertEqual(w.distance_mm_label.text(), '2 mm')
        w.list.setCurrentRow(1)
        self.assertEqual(w.reference_spin.value(), 0)
        self.assertEqual(w.distance_mm_label.text(), '— mm')
        w.reference_spin.setValue(51.234)
        w.open_folder(self.root)
        self.assertEqual(w.reference_spin.value(), 49)
        self.assertEqual(w.distance_mm_label.text(), '2 mm')
        w.reference_spin.setValue(0)
        self.assertIsNone(w.current.reference_width_px)
        self.assertEqual(w.distance_mm_label.text(), '— mm')
        saved = json.loads(w.store.path.read_text())
        self.assertIsNone(saved['images']['a.png']['reference_width_px'])
        self.assertEqual(saved['images']['b.png']['reference_width_px'], 51.234)

    def test_reference_tool_horizontal_zoom_cancel_and_coincident_points(self):
        w = self.window
        original_line, original_roi = w.current.line, w.current.roi
        for zoom in (1, 4, 8):
            w.reference_spin.setValue(20)
            w.viewer.set_zoom(zoom)
            w.viewer.centerOn(50, 70)
            self.app.processEvents()
            QTest.mouseClick(w.draw_buttons['reference'], Qt.MouseButton.LeftButton)
            self.click_pixel(70, 40)
            self.click_pixel(70, 40)
            self.assertEqual(w.reference_spin.value(), 20)
            self.assertEqual(w.viewer.first, (70, 40))
            self.click_pixel(21, 40)
            self.assertEqual(w.reference_spin.value(), 49)
            self.assertEqual(w.current.distance_mm, 2)
            self.assertIsNone(w.viewer.mode)
            self.assertEqual(len(w.viewer.overlays), 1)
            self.assertEqual(w.current.line, original_line)
            self.assertEqual(w.current.roi, original_roi)
            w.viewer.set_mode('reference')
            self.click_pixel(50, 40)
            QTest.keyClick(w.viewer, Qt.Key.Key_Escape)
            self.assertEqual(w.reference_spin.value(), 49)
            self.assertFalse(w.draw_buttons['reference'].isChecked())
        self.assertNotIn('reference_line', json.loads(w.store.path.read_text())['images']['a.png'])

    def test_reference_tool_free_direction_preview_rounding_and_persistence(self):
        w = self.window
        cases = [((30, 40), (60, 80), 50), ((50, 40), (50, 90), 50),
                 ((40, 40), (41, 41), 1.414)]
        for zoom in (1, 4, 8):
            w.viewer.set_zoom(zoom)
            w.viewer.centerOn(50, 65)
            self.app.processEvents()
            for a, b, expected in cases:
                for first, second in [(a, b), (b, a)]:
                    w.viewer.set_mode('reference')
                    self.click_pixel(*first)
                    w.viewer.hover = second
                    w.viewer.redraw()
                    preview = w.viewer.overlays[-1].line()
                    self.assertEqual((preview.x1(), preview.y1()), (first[0]+.5, first[1]+.5))
                    self.assertEqual((preview.x2(), preview.y2()), (second[0]+.5, second[1]+.5))
                    self.click_pixel(*second)
                    self.assertEqual(w.reference_spin.value(), expected)
                    self.assertEqual(w.current.reference_width_px, expected)
                    self.assertAlmostEqual(w.current.distance_mm, 14*7/expected)
                    self.assertIsNone(w.viewer.mode)
                    self.assertEqual(len(w.viewer.overlays), 1)
        w.open_folder(self.root)
        self.assertEqual(w.reference_spin.value(), 1.414)
        self.assertEqual(w.current.reference_width_px, 1.414)

    def test_reference_survives_rotation_and_erase_but_not_resize(self):
        w = self.window
        w.reference_spin.setValue(49)
        w.erase('line')
        w.erase('roi')
        w.rotate(90)
        self.assertEqual(w.current.reference_width_px, 49)
        self.assertEqual(w.distance_mm_label.text(), '— mm')
        changed = QImage(400, 320, QImage.Format.Format_RGB32)
        changed.fill(Qt.GlobalColor.white)
        changed.save(str(self.root / 'a.png'))
        with patch.object(QMessageBox, 'warning'):
            w.open_folder(self.root)
        self.assertIsNone(w.current.reference_width_px)
        self.assertEqual(w.reference_spin.value(), 0)

    def test_empty_and_unreadable_image_clear_reference_and_mm_labels(self):
        w = self.window
        w.reference_spin.setValue(49)
        (self.root / 'b.png').write_bytes(b'invalida')
        with patch.object(QMessageBox, 'warning'):
            w.list.setCurrentRow(1)
        self.assertEqual(w.reference_spin.value(), 0)
        self.assertEqual(w.distance_mm_label.text(), '— mm')
        empty = self.root / 'empty'
        empty.mkdir()
        w.open_folder(empty)
        self.assertFalse(w.reference_spin.isEnabled())
        self.assertEqual(w.distance_mm_label.text(), '— mm')

    def test_multiline_fits_and_matches_export_without_reference_preview(self):
        w = self.window
        w.reference_spin.setValue(49)
        for width, height in [(1200, 1600), (30, 20), (2000, 20), (20, 2000)]:
            text = distance_caption(w.current)
            font, origin, scale = distance_text_layout(text, QRectF(0, 0, width, height))
            box = distance_text_bounds(text, font)
            actual = QTransform().translate(origin.x(), origin.y()).scale(scale, scale).mapRect(box)
            self.assertLessEqual(actual.right(), width+.00001)
            self.assertLessEqual(actual.bottom(), height+.00001)
        for reference in (None, 49):
            w.current.reference_width_px = reference
            w.viewer.redraw()
            w.viewer.set_mode('reference')
            w.viewer.first, w.viewer.hover = (1, 1), (150, 90)
            w.viewer.redraw()
            target = self.root / 'export.png'
            export_image(self.root / 'a.png', target, w.current)
            w.viewer.cancel()
            expected = QImage(200, 160, QImage.Format.Format_ARGB32_Premultiplied)
            expected.fill(Qt.GlobalColor.transparent)
            painter = QPainter(expected)
            rect = QRectF(0, 0, 200, 160)
            w.viewer.scene().render(painter, rect, rect)
            painter.end()
            actual = QImage(str(target)).convertToFormat(expected.format())
            self.assertEqual(actual, expected)
            self.assertEqual(len(complete_measurements(w.store.root, w.paths, w.store.items)), 1)


if __name__ == '__main__':
    unittest.main()
