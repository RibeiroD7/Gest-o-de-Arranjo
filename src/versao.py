"""Versão publicada do aplicativo e onde encontrar as releases.

Módulo à parte porque o release.sh reescreve VERSAO_APP a cada publicação:
uma linha previsível, num arquivo que não muda por outro motivo.
"""

from __future__ import annotations

VERSAO_APP = "2.12.3"

URL_API_RELEASE = (
    "https://api.github.com/repos/RibeiroD7/Gest-o-de-Arranjo/releases/latest"
)
URL_RELEASES = "https://github.com/RibeiroD7/Gest-o-de-Arranjo/releases/latest"
