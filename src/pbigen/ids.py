"""Identificadores deterministas.

PBIR exige nombres hexadecimales para páginas y visuales. Derivarlos del spec
(y no de un generador aleatorio) hace que dos generaciones del mismo spec
produzcan ficheros idénticos y diffs vacíos.
"""

from __future__ import annotations

import hashlib


def hex_id(*parts: str, length: int = 20) -> str:
    """Devuelve `length` caracteres hexadecimales en minúscula derivados de `parts`."""
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]
