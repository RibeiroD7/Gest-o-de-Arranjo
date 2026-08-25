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
import atualizacao  # noqa: E402

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
        assert atualizacao._url_instalador_plataforma(ASSETS) == "https://exemplo/arm64.apk"

    def test_android_antigo_recebe_o_apk_de_32_bits(self, celular):
        celular("armv7l")
        assert atualizacao._url_instalador_plataforma(ASSETS) == "https://exemplo/32bits.apk"

    def test_arquitetura_desconhecida_fica_com_o_arm64(self, celular):
        # Praticamente todo aparelho em uso é arm64; na dúvida, é o palpite certo.
        celular("")
        assert atualizacao._url_instalador_plataforma(ASSETS) == "https://exemplo/arm64.apk"

    def test_computador_recebe_o_instalador_do_sistema(self):
        esperado = (
            "https://exemplo/windows.exe"
            if sys.platform.startswith("win")
            else "https://exemplo/linux.tar.gz"
        )
        assert atualizacao._url_instalador_plataforma(ASSETS) == esperado

    def test_release_sem_arquivo_para_a_plataforma(self):
        assert atualizacao._url_instalador_plataforma([]) is None


def test_baixar_no_celular_usa_o_abrir_url_que_espera_a_corrotina(celular, monkeypatch):
    """No Android, page.launch_url sem await não faz nada — em silêncio.

    Foi o bug do botão "Baixar" que não respondia: a chamada estava direta,
    fora do abrir_url, que é quem embrulha a corrotina no run_task.
    """
    celular("aarch64")
    chamadas = []
    monkeypatch.setattr(atualizacao, "abrir_url", lambda page, url: chamadas.append(url))

    atualizacao._baixar_atualizacao(object(), "https://exemplo/app.apk")
    assert chamadas == ["https://exemplo/app.apk"]

    atualizacao._baixar_atualizacao(object(), None)
    assert chamadas[-1] == atualizacao.URL_RELEASES


def test_ninguem_chama_launch_url_por_fora_do_ui_comuns():
    """Guarda a regra: quem abre URL usa abrir_url, que trata o celular."""
    import ast
    import pathlib

    problemas = []
    for arquivo in sorted(pathlib.Path("src").rglob("*.py")):
        if arquivo.name == "ui_comuns.py":
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if (isinstance(no, ast.Attribute) and no.attr == "launch_url"
                    and isinstance(no.value, ast.Name) and no.value.id == "page"):
                problemas.append(f"{arquivo.name}:{no.lineno}")
    assert not problemas, (
        "page.launch_url fora do ui_comuns: no celular ela é assíncrona e "
        "sem await não abre nada — " + ", ".join(problemas)
    )
