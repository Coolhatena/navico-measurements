import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QPointF, QPoint
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from navico.model import Measurement, make_roi, pixel_at
from navico.storage import Store, find_images
from navico.viewer import ImageView
from navico.app import MainWindow


class GeometryTests(unittest.TestCase):
    def test_horizontal_distance(self):
        for x, roi, expected in [(10, (20, 0, 41, 5), 20.5), (50, (20, 0, 40, 5), 20), (30, (20, 0, 40, 5), 0)]:
            record = Measurement(line=(x, 900, 999), roi=roi)
            self.assertEqual(record.distance, expected)
            record.line_width, record.roi_width = 50, 1
            self.assertEqual(record.distance, expected)

    def test_missing_shapes(self):
        self.assertIsNone(Measurement().distance)
        self.assertIsNone(Measurement(line=(1, 0, 2)).distance)

    def test_roi_order_and_degenerate(self):
        for a, b in [((1, 2), (7, 8)), ((7, 8), (1, 2)), ((1, 8), (7, 2)), ((7, 2), (1, 8))]:
            self.assertEqual(make_roi(a, b), (1, 2, 7, 8))
        self.assertIsNone(make_roi((1, 1), (1, 5)))

    def test_pixels(self):
        self.assertEqual(pixel_at(0, 0, 10, 10), (0, 0))
        self.assertEqual(pixel_at(9.99, 2.5, 10, 10), (9, 2))
        self.assertIsNone(pixel_at(-.01, 0, 10, 10))
        self.assertIsNone(pixel_at(10, 0, 10, 10))

    def test_validation(self):
        valid = Measurement(size=(100, 50), rotation=90, line=(49, 0, 99), roi=(1, 1, 40, 90))
        self.assertEqual(Measurement.from_dict(valid.to_dict()), valid)
        for key, value in [('rotation', 45), ('line_width', True), ('roi_width', 51), ('line', (50, 0, 5)), ('roi', (1, 1, 1, 2))]:
            data = valid.to_dict()
            data[key] = value
            with self.assertRaises(ValueError):
                Measurement.from_dict(data)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_nested_reopen_and_scan(self):
        store = Store(self.root)
        for sub in ['CAPA A', 'CAPA B']:
            (self.root / sub).mkdir()
            (self.root / sub / 'igual.JPG').touch()
            store.items[f'{sub}/igual.JPG'] = Measurement(size=(100, 50), rotation=90, line=(10, 1, 20), roi=(15, 1, 30, 20), line_width=5)
        (self.root / 'ignorar.txt').touch()
        store.dirty = True
        store.save()
        self.assertFalse(store.dirty)
        loaded = Store(self.root)
        loaded.load()
        self.assertEqual(loaded.items, store.items)
        self.assertEqual(len(find_images(self.root)), 2)

    def test_corrupt_file_protected(self):
        store = Store(self.root)
        for content in ['{', '[]', '{"version": 2, "images": {}}', '{"version": 1, "images": {"../escape": {}}}']:
            store.path.write_text(content)
            with self.assertRaises(ValueError):
                store.load()
            with self.assertRaises(OSError):
                store.save()
            self.assertEqual(store.path.read_text(), content)

    def test_atomic_failure_retains_previous(self):
        store = Store(self.root)
        store.save()
        original = store.path.read_bytes()
        store.items['x.jpg'] = Measurement()
        store.dirty = True
        with patch('navico.storage.os.replace', side_effect=OSError('Disco lleno')):
            with self.assertRaises(OSError):
                store.save()
        self.assertEqual(store.path.read_bytes(), original)
        self.assertTrue(store.dirty)
        self.assertEqual(list(self.root.glob('*.tmp')), [])


class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.record = Measurement(size=(100, 80))
        self.view = ImageView()
        self.view.resize(700, 600)
        self.image = QImage(100, 80, QImage.Format.Format_RGB32)
        self.image.fill(Qt.GlobalColor.white)
        self.view.show()
        self.view.load_image(self.image, self.record)
        self.app.processEvents()
        self.addCleanup(self.view.close)

    def click_pixel(self, x, y):
        pos = self.view.mapFromScene(QPointF(x + .5, y + .5))
        # Las posiciones de QTest son enteras; cerca de una frontera, redondear
        # el centro transformado puede caer en el píxel adyacente al 100 %.
        candidates = [pos + QPoint(dx, dy) for dx in (0, -1, 1) for dy in (0, -1, 1)]
        pos = next(p for p in candidates if self.view.point_at(p) == (x, y))
        QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton, pos=pos)

    def test_zoom_preserves_pixel_and_line_x(self):
        for zoom in (1, 2, 8, 16):
            self.view.set_zoom(zoom)
            self.view.centerOn(40.5, 30.5)
            self.app.processEvents()
            self.view.set_mode('line')
            self.click_pixel(20, 20)
            self.click_pixel(35, 40)
            self.assertEqual(self.record.line, (20, 20, 40))

    def test_roi_reverse_escape_and_preview(self):
        self.view.set_zoom(4)
        self.view.set_mode('roi')
        self.click_pixel(70, 60)
        p = self.view.mapFromScene(QPointF(10.5, 10.5))
        QTest.mouseMove(self.view.viewport(), p)
        self.assertIsNone(self.record.roi)
        self.click_pixel(10, 10)
        self.assertEqual(self.record.roi, (10, 10, 70, 60))
        self.view.set_mode('roi')
        self.click_pixel(20, 20)
        QTest.keyClick(self.view, Qt.Key.Key_Escape)
        self.assertIsNone(self.view.first)
        self.assertEqual(self.record.roi, (10, 10, 70, 60))

    def test_cursor_and_pan(self):
        messages = []
        self.view.coordinates.connect(messages.append)
        self.view.set_zoom(16)
        self.view.centerOn(50, 40)
        QTest.mouseMove(self.view.viewport(), self.view.mapFromScene(QPointF(50.5, 40.5)))
        self.assertEqual(messages[-1], 'X: 50   Y: 40')
        before = self.view.mapToScene(QPoint(300, 250))
        QTest.keyPress(self.view, Qt.Key.Key_Space)
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(300, 250))
        QTest.mouseMove(self.view.viewport(), QPoint(340, 280))
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(340, 280))
        QTest.keyRelease(self.view, Qt.Key.Key_Space)
        self.assertNotEqual(before, self.view.mapToScene(QPoint(300, 250)))
        self.assertIsNone(self.record.line)

    def test_wheel_zoom_and_limits(self):
        self.view.set_zoom(2)
        event = QWheelEvent(QPointF(300, 250), QPointF(300, 250), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(self.view.viewport(), event)
        self.assertAlmostEqual(self.view.transform().m11(), 2.5)
        self.view.set_zoom(100)
        self.assertEqual(self.view.transform().m11(), 64)
        self.view.set_zoom(0)
        self.assertAlmostEqual(self.view.transform().m11(), .01)


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = QImage(100, 80, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        image.save(str(self.root / 'test.png'))
        self.original = (self.root / 'test.png').read_bytes()
        self.window = MainWindow()
        self.window.show()
        self.window.open_folder(self.root)
        self.addCleanup(self.window.close)

    def test_rotation_cancel_confirm_and_reopen(self):
        w = self.window
        w.current.line = (10, 1, 30)
        w.current.roi = (40, 10, 61, 20)
        w.changed()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            w.rotate(90)
        self.assertEqual(w.current.distance, 40.5)
        self.assertEqual(w.current.rotation, 0)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            w.rotate(90)
        self.assertIsNone(w.current.line)
        self.assertIsNone(w.current.roi)
        self.assertEqual(w.viewer.pixmap.pixmap().width(), 80)
        w.current.line = (1, 0, 50)
        w.current.roi = (10, 1, 21, 40)
        w.set_width('line_width', 7)
        w.open_folder(self.root)
        self.assertEqual(w.current.rotation, 90)
        self.assertEqual(w.current.line_width, 7)
        self.assertEqual(w.current.distance, 14.5)
        self.assertEqual((self.root / 'test.png').read_bytes(), self.original)

    def test_dimension_change_invalidates(self):
        w = self.window
        w.current.line = (10, 1, 30)
        w.changed()
        image = QImage(200, 160, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        image.save(str(self.root / 'test.png'))
        with patch.object(QMessageBox, 'warning') as warning:
            w.open_folder(self.root)
        warning.assert_called_once()
        self.assertIsNone(w.current.line)
        self.assertEqual(w.current.size, (200, 160))

    def test_failed_save_blocks_closing_and_switching(self):
        w = self.window
        w.current.line = (10, 1, 30)
        with patch.object(Store, 'save', side_effect=OSError('Sin permiso')), patch.object(QMessageBox, 'warning'), patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Cancel):
            w.changed()
            self.assertTrue(w.store.dirty)
            self.assertFalse(w.allow_leave())
            self.assertFalse(w.close())
        self.assertTrue(w.flush())

    def test_invalid_configuration_is_read_only(self):
        path = self.root / '.navico-measurements.json'
        path.write_text('{roto')
        with patch.object(QMessageBox, 'warning'):
            self.window.open_folder(self.root)
        self.assertTrue(self.window.store.blocked)
        self.assertFalse(self.window.widths['line_width'].isEnabled())
        self.assertFalse(self.window.reference_spin.isEnabled())
        self.assertFalse(self.window.rotate_left.isEnabled())
        self.assertTrue(all(button.isEnabled() for button in self.window.navigation_controls))
        self.assertFalse(any(button.isEnabled() for button in self.window.draw_buttons.values()))
        self.assertIsNone(self.window.viewer.mode)
        self.assertEqual(path.read_text(), '{roto')

    def test_unreadable_image_does_not_crash(self):
        (self.root / 'test.png').write_bytes(b'no es imagen')
        with patch.object(QMessageBox, 'warning') as warning:
            self.window.select_image(0)
        warning.assert_called_once()
        self.assertIsNone(self.window.current)
        self.assertIsNone(self.window.viewer.pixmap)

    def test_tool_buttons_follow_cancel_complete_and_image_change(self):
        w = self.window
        QTest.mouseClick(w.draw_buttons['line'], Qt.MouseButton.LeftButton)
        self.assertTrue(w.draw_buttons['line'].isChecked())
        self.assertFalse(w.draw_buttons['roi'].isChecked())
        QTest.keyClick(w.viewer, Qt.Key.Key_Escape)
        self.assertFalse(any(b.isChecked() for b in w.draw_buttons.values()))
        QTest.mouseClick(w.draw_buttons['roi'], Qt.MouseButton.LeftButton)
        self.app.processEvents()
        for x, y in [(10, 10), (40, 50)]:
            pos = w.viewer.mapFromScene(QPointF(x+.5, y+.5))
            QTest.mouseClick(w.viewer.viewport(), Qt.MouseButton.LeftButton, pos=pos)
        self.assertIsNotNone(w.current.roi)
        self.assertFalse(w.draw_buttons['roi'].isChecked())
        QTest.mouseClick(w.draw_buttons['line'], Qt.MouseButton.LeftButton)
        w.select_image(0)
        self.assertFalse(any(b.isChecked() for b in w.draw_buttons.values()))

    def test_keyboard_list_navigation_and_metadata(self):
        w = self.window
        self.window.base_image.save(str(self.root / 'second.png'))
        w.open_folder(self.root)
        self.assertEqual(w.count_label.text(), '2 imágenes')
        self.assertEqual(w.list.item(0).data(Qt.ItemDataRole.UserRole), 'second.png')
        self.assertEqual(w.list.item(0).toolTip(), str((self.root / 'second.png').resolve()))
        w.list.setFocus()
        QTest.keyClick(w.list, Qt.Key.Key_Down)
        self.assertEqual(w.list.currentRow(), 1)
        self.assertEqual(w.file_label.full_text, 'test.png')
        self.assertEqual(w.dimensions_label.text(), '100 × 80 px')
        w.rotate(90)
        self.assertEqual(w.dimensions_label.text(), '80 × 100 px')

    def test_empty_folder_disables_all_image_controls(self):
        empty = self.root / 'vacía'
        empty.mkdir()
        self.window.open_folder(empty)
        self.assertEqual(self.window.count_label.text(), '0 imágenes')
        self.assertFalse(any(b.isEnabled() for b in self.window.edit_controls + self.window.navigation_controls))
        self.assertFalse(self.window.viewer.empty_label.isHidden())
        self.assertEqual(self.window.distance_label.text(), '— px')
        self.app.processEvents()
        self.assertEqual(self.window.viewer.horizontalScrollBar().maximum(), 0)
        self.assertEqual(self.window.viewer.verticalScrollBar().maximum(), 0)


if __name__ == '__main__':
    unittest.main()
