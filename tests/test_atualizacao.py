"""Escolha do arquivo de atualização conforme o aparelho.

O botão "Buscar atualizações" em Ajustes baixa um arquivo por plataforma. No
Android o APK é publicado por arquitetura, e entregar o de 32 bits a um
aparelho arm64 (ou o contrário) faz a instalação falhar — por isso a escolha
tem teste.
"""

import platform
import sys

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import armazenamento  # noqa: E402
import main  # noqa: E402

ASSETS = [
    {"name": "GestaoArranjo-2.11.2-android-32bits.apk",
     "browser_download_url": "https://exemplo/32bits.apk"},
    {"name": "GestaoArranjo-2.11.2-android.apk",
     "browser_download_url": "https://exemplo/arm64.apk"},
    {"name": "GestaoArranjo-2.11.2-linux.tar.gz",
     "browser_download_url": "https://exemplo/linux.tar.gz"},
    {"name": "GestaoArranjo-2.11.2-windows-instalador.exe",
     "browser_download_url": "https://exemplo/windows.exe"},
]


@pytest.fixture
def celular(monkeypatch):
    """Coloca o app em modo celular e devolve o ajuste da arquitetura."""
    armazenamento.definir_layout_mobile(True)
    yield lambda maquina: monkeypatch.setattr(platform, "machine", lambda: maquina)
    armazenamento.definir_layout_mobile(False)


class TestUrlInstaladorPlataforma:
    def test_android_atual_recebe_o_apk_arm64(self, celular):
        celular("aarch64")
        assert main._url_instalador_plataforma(ASSETS) == "https://exemplo/arm64.apk"

    def test_android_antigo_recebe_o_apk_de_32_bits(self, celular):
        celular("armv7l")
        assert main._url_instalador_plataforma(ASSETS) == "https://exemplo/32bits.apk"

    def test_arquitetura_desconhecida_fica_com_o_arm64(self, celular):
        # Praticamente todo aparelho em uso é arm64; na dúvida, é o palpite certo.
        celular("")
        assert main._url_instalador_plataforma(ASSETS) == "https://exemplo/arm64.apk"

    def test_computador_recebe_o_instalador_do_sistema(self):
        esperado = (
            "https://exemplo/windows.exe"
            if sys.platform.startswith("win")
            else "https://exemplo/linux.tar.gz"
        )
        assert main._url_instalador_plataforma(ASSETS) == esperado

    def test_release_sem_arquivo_para_a_plataforma(self):
        assert main._url_instalador_plataforma([]) is None
