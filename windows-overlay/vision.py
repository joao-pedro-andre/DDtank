"""Detecção visual experimental dos elementos do HUD do DDTank.

As regiões são calibradas pelo usuário no overlay. Os resultados são estimativas:
não usar como confirmação de tiro até validar em jogo.
"""
from __future__ import annotations

from collections import Counter
from PIL import Image
import colorsys


def _hsv_pixels(image: Image.Image):
    rgb = image.convert("RGB")
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = rgb.getpixel((x, y))
            yield x, y, colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)


def _components(mask, width, height, min_area=2):
    seen = set()
    comps = []
    for y in range(height):
        for x in range(width):
            if not mask[y][x] or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            pts = []
            while stack:
                px, py = stack.pop()
                pts.append((px, py))
                for nx, ny in ((px-1,py),(px+1,py),(px,py-1),(px,py+1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny][nx] and (nx,ny) not in seen:
                        seen.add((nx,ny))
                        stack.append((nx,ny))
            if len(pts) >= min_area:
                comps.append(pts)
    return comps


def _center_of_largest(mask, width, height, min_area=2):
    comps = _components(mask, width, height, min_area)
    if not comps:
        return None
    pts = max(comps, key=len)
    return (sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts), len(pts))


def detect_minimap(image: Image.Image):
    """Localiza marcador azul do jogador e marcador vermelho do alvo.

    A escala vem do espaçamento mais comum entre linhas verticais claras.
    Cada quadrícula é considerada 10 unidades, conforme informado pelo jogador.
    """
    w, h = image.size
    blue = [[False] * w for _ in range(h)]
    red = [[False] * w for _ in range(h)]
    for x, y, (hue, sat, val) in _hsv_pixels(image):
        blue[y][x] = 0.52 <= hue <= 0.72 and sat >= 0.42 and val >= 0.30
        red[y][x] = (hue <= 0.055 or hue >= 0.94) and sat >= 0.50 and val >= 0.30
    player = _center_of_largest(blue, w, h, 2)
    target = _center_of_largest(red, w, h, 2)

    # Linhas de grade: colunas com muitos pixels quase brancos.
    bright_cols = []
    rgb_image = image.convert("RGB")
    pixels = rgb_image.load()
    for x in range(w):
        count = 0
        for y in range(h):
            r, g, b = pixels[x, y]
            if min(r, g, b) >= 185 and max(r, g, b) - min(r, g, b) <= 35:
                count += 1
        if count >= max(5, int(h * 0.28)):
            bright_cols.append(x)
    groups = []
    for x in bright_cols:
        if not groups or x > groups[-1][-1] + 1:
            groups.append([x])
        else:
            groups[-1].append(x)
    centers = [sum(g) / len(g) for g in groups if len(g) <= 5]
    gaps = [centers[i+1] - centers[i] for i in range(len(centers)-1)]
    spacing = None
    if gaps:
        # Remove distâncias muito pequenas/longas e usa a mediana.
        valid = [g for g in gaps if 4 <= g <= w * 0.35]
        if valid:
            valid.sort()
            spacing = valid[len(valid)//2]

    distance = None
    if player and target and spacing and spacing > 0:
        distance = abs(target[0] - player[0]) / spacing * 10
    return {
        "player": player,
        "target": target,
        "grid_spacing_px": spacing,
        "distance": distance,
    }



def detect_wind_direction(image: Image.Image):
    """Estima a direção da seta do indicador superior 'Força Vento'.

    A calibração deve incluir somente a seta e o número do vento ATUAL,
    excluindo o rótulo e, principalmente, a linha 'rod.ant.'.
    Retorna 'left', 'right' ou None quando a evidência visual é fraca.
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    if w < 12 or h < 8:
        return None

    # A seta é clara/neutra; céu azul e dígitos coloridos ficam de fora.
    mask = [[False] * w for _ in range(h)]
    pixels = rgb.load()
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if min(r, g, b) >= 145 and max(r, g, b) - min(r, g, b) <= 65:
                mask[y][x] = True

    components = _components(mask, w, h, min_area=max(12, int(w * h * 0.025)))
    if not components:
        return None

    # Use a maior massa clara, que deve ser o corpo da seta.
    points = max(components, key=len)
    xs = [p[0] for p in points]
    x_min, x_max = min(xs), max(xs)
    if x_max - x_min < w * 0.35:
        return None

    # A ponta da seta torna um dos lados do ícone visualmente mais preenchido.
    # O recorte precisa conter o ícone inteiro e não deve incluir 'rod.ant.'.
    column_counts = [sum(1 for x, _ in points if x == col) for col in range(x_min, x_max + 1)]
    span = len(column_counts)
    edge_width = max(2, int(span * 0.32))
    left_mass = sum(column_counts[:edge_width])
    right_mass = sum(column_counts[-edge_width:])
    larger = max(left_mass, right_mass)
    smaller = min(left_mass, right_mass)
    if larger == 0 or (larger - smaller) / larger < 0.12:
        return None

    return "left" if left_mass > right_mass else "right"


def detect_red_marker_x(image: Image.Image):
    """Retorna x do maior componente vermelho (marcador da barra de força)."""
    w, h = image.size
    mask = [[False] * w for _ in range(h)]
    for x, y, (hue, sat, val) in _hsv_pixels(image):
        mask[y][x] = (hue <= 0.055 or hue >= 0.94) and sat >= 0.55 and val >= 0.35
    marker = _center_of_largest(mask, w, h, 3)
    return marker[0] if marker else None
