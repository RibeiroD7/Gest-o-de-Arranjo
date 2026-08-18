"""copiar_imagem_para_area_transferencia: precisa funcionar no app instalado.

O WhatsApp Web não tem como anexar arquivo por um link — por isso a imagem
vai para a área de transferência do Windows (Ctrl+V na conversa resolve).

A primeira versão usava pywin32: funcionava rodando do código-fonte, mas não
no instalador (o Flet não empacota os .pyd nem as DLLs de pywin32_system32),
e o `except` silencioso escondia a falha — o app voltava a mandar só texto.
Por isso o teste principal roda com pywin32 fora do caminho: garante que a
cópia depende só de ctypes, da biblioteca padrão.
"""

import platform
import sys

import pytest
from PIL import Image

from png_oradores import copiar_imagem_para_area_transferencia

no_windows = platform.system() == "Windows"


def _criar_png(tmp_path):
    caminho = tmp_path / "designacao.png"
    Image.new("RGB", (120, 60), "#0D47A1").save(caminho, format="PNG")
    return caminho


@pytest.mark.skipif(not no_windows, reason="área de transferência só no Windows")
def test_copia_sem_pywin32(tmp_path, monkeypatch):
    """O caso do app empacotado: sem pywin32, a cópia ainda precisa funcionar."""
    monkeypatch.setitem(sys.modules, "win32clipboard", None)
    origem = _criar_png(tmp_path)

    assert copiar_imagem_para_area_transferencia(origem) is True

    from PIL import ImageGrab

    colada = ImageGrab.grabclipboard()
    assert colada is not None, "nada foi parar na área de transferência"
    assert colada.size == Image.open(origem).size
    assert colada.convert("RGB").getpixel((0, 0)) == (13, 71, 161)


def test_fora_do_windows_devolve_false_sem_lancar(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert copiar_imagem_para_area_transferencia(_criar_png(tmp_path)) is False


def test_arquivo_inexistente_nao_lanca(tmp_path, monkeypatch):
    """Falhar aqui não pode travar o envio — devolve False e o app manda texto."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    assert copiar_imagem_para_area_transferencia(tmp_path / "nao-existe.png") is False
