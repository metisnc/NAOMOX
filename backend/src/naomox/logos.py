"""Logos de jeux rognés : les PNG du pack WiPi ont des marges transparentes très variables,
ce qui donne des tailles apparentes différentes d'une tuile à l'autre. On recadre une fois
sur le contenu visible (canal alpha, ou couleur du fond pour les images opaques) et on met
le résultat en cache."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("naomox.logos")

ALPHA_THRESHOLD = 16  # pixels quasi transparents ignorés
BG_THRESHOLD = 28  # écart à la couleur du fond pour les images sans transparence
MARGIN = 0.03  # marge conservée autour du contenu


def trimmed(source: Path, cache_dir: Path) -> Path:
    """Chemin d'une version recadrée de `source` (générée si absente ou périmée).
    Retourne `source` si le recadrage est impossible (format non géré, Pillow absent…)."""
    target = cache_dir / (source.stem + ".png")
    try:
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            return target
        from PIL import Image, ImageChops

        with Image.open(source) as im:
            im.load()
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                rgba = im.convert("RGBA")
                bbox = rgba.getchannel("A").point(lambda a: 255 if a > ALPHA_THRESHOLD else 0).getbbox()
            else:
                rgba = im.convert("RGBA")
                rgb = im.convert("RGB")
                bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
                diff = ImageChops.difference(rgb, bg).convert("L")
                bbox = diff.point(lambda v: 255 if v > BG_THRESHOLD else 0).getbbox()
            if bbox:
                x0, y0, x1, y1 = bbox
                mx, my = int((x1 - x0) * MARGIN), int((y1 - y0) * MARGIN)
                w, h = rgba.size
                rgba = rgba.crop((max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)))
            cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            rgba.save(tmp, "PNG", optimize=True)
            os.replace(tmp, target)
        return target
    except Exception as e:  # le logo d'origine reste utilisable
        log.debug("recadrage impossible pour %s : %s", source.name, e)
        return source
