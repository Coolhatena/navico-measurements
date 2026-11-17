"""Geometría en coordenadas de centros de píxel (sin dependencia de Qt)."""
from dataclasses import asdict, dataclass
import math


@dataclass
class Measurement:
    rotation: int = 0
    size: tuple[int, int] | None = None
    line: tuple[int, int, int] | None = None  # x, y superior, y inferior
    roi: tuple[int, int, int, int] | None = None
    line_width: int = 2
    roi_width: int = 2
    reference_width_px: float | None = None

    @property
    def distance(self):
        if self.line is None or self.roi is None:
            return None
        return abs((self.roi[0] + self.roi[2]) / 2 - self.line[0])

    @property
    def distance_mm(self):
        if self.distance is None or self.reference_width_px is None:
            return None
        return self.distance * 7 / self.reference_width_px

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        fields = set(cls.__dataclass_fields__)
        if not isinstance(data, dict) or set(data) not in (fields, fields - {'reference_width_px'}):
            raise ValueError("Estructura de medición inválida")
        reference = data.get('reference_width_px')
        if reference is not None:
            try:
                valid = type(reference) in (int, float) and math.isfinite(reference) and reference > 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError('Tamaño de referencia inválido')
        def integers(value, length):
            return isinstance(value, (list, tuple)) and len(value) == length and all(type(n) is int for n in value)
        if type(data['rotation']) is not int or data['rotation'] not in (0, 90, 180, 270):
            raise ValueError("Rotación inválida")
        if any(type(data[k]) is not int or not 1 <= data[k] <= 50 for k in ('line_width', 'roi_width')):
            raise ValueError("Grosor inválido")
        size = data['size']
        if size is not None and (not integers(size, 2) or min(size) < 1):
            raise ValueError("Dimensiones inválidas")
        for key, length in [('line', 3), ('roi', 4)]:
            if data[key] is not None and not integers(data[key], length):
                raise ValueError("Coordenadas inválidas")
        obj = cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in data.items()})
        if (obj.line or obj.roi) and obj.size is None:
            raise ValueError("Faltan dimensiones")
        if obj.size:
            w, h = obj.size if obj.rotation % 180 == 0 else obj.size[::-1]
            if obj.line:
                x, a, b = obj.line
                if not (0 <= x < w and 0 <= a < b < h):
                    raise ValueError("Línea fuera de límites")
            if obj.roi:
                a, b, c, d = obj.roi
                if not (0 <= a < c < w and 0 <= b < d < h):
                    raise ValueError("ROI fuera de límites")
        return obj


def format_mm(value):
    return f'{value:.2f}'.rstrip('0').rstrip('.') if value is not None else '—'


def pixel_at(x, y, width, height):
    if not (0 <= x < width and 0 <= y < height):
        return None
    return math.floor(x), math.floor(y)


def make_roi(a, b):
    x1, x2 = sorted((a[0], b[0]))
    y1, y2 = sorted((a[1], b[1]))
    return (x1, y1, x2, y2) if x1 < x2 and y1 < y2 else None
