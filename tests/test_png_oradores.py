"""copiar_imagem_para_area_transferencia: nunca pode travar o envio.

O WhatsApp Web não tem como anexar arquivo por um link — por isso a imagem
vai para a área de transferência do Windows (Ctrl+V na conversa resolve).
Fora do Windows, ou sem o pywin32, a função precisa devolver False (não
lançar), para o chamador cair no texto pré-preenchido de antes.
"""

from PIL import Image

from png_oradores import copiar_imagem_para_area_transferencia


def _criar_png(tmp_path):
    caminho = tmp_path / "designacao.png"
    Image.new("RGB", (40, 20), "#FFFFFF").save(caminho, format="PNG")
    return caminho


def test_fora_do_windows_devolve_false_sem_lancar(tmp_path, monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert copiar_imagem_para_area_transferencia(_criar_png(tmp_path)) is False


def test_arquivo_inexistente_nao_lanca(tmp_path, monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    resultado = copiar_imagem_para_area_transferencia(tmp_path / "nao-existe.png")
    assert resultado is False


def test_no_windows_devolve_bool_sem_lancar(tmp_path, monkeypatch):
    """No Windows real: com pywin32 devolve True, sem ele devolve False —
    nos dois casos, sem exceção (é o que garante não travar o envio)."""
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    resultado = copiar_imagem_para_area_transferencia(_criar_png(tmp_path))
    assert resultado in (True, False)
