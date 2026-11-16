"""Carga validada y reemplazo atómico del archivo de mediciones."""
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from .model import Measurement

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}


def find_images(root):
    return sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS),
                  key=lambda p: p.relative_to(root).as_posix().casefold())


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / '.navico-measurements.json'
        self.items = {}
        self.blocked = False
        self.dirty = False

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('images'), dict):
                raise ValueError('Formato o versión no admitidos')
            items = {}
            for key, value in data['images'].items():
                path = PurePosixPath(key)
                if not key or path.is_absolute() or '..' in path.parts or '\\' in key:
                    raise ValueError('Ruta relativa inválida')
                items[key] = Measurement.from_dict(value)
            self.items = items
        except (OSError, ValueError, TypeError) as exc:
            self.blocked = True
            raise ValueError(f'No se pudo cargar {self.path.name}: {exc}') from exc

    def save(self):
        if self.blocked:
            raise OSError('El archivo de configuración es inválido. No se sobrescribirá. Respalda o corrige el archivo y vuelve a abrir la carpeta.')
        payload = json.dumps({'version': 1, 'images': {k: v.to_dict() for k, v in self.items.items()}}, ensure_ascii=False, indent=2)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.root, prefix='.navico-', suffix='.tmp', delete=False) as file:
                temp = file.name
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.path)
            self.dirty = False
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
