"""Testes da decisão de layout (celular vs. desktop).

Regressão coberta aqui: o desktop empacotado também define
FLET_APP_STORAGE_DATA, então o layout NÃO pode ser deduzido dessa variável —
senão o app de PC instalado abre com a interface de celular.
"""

import armazenamento


def _restaurar():
    armazenamento._LAYOUT_MOBILE = None


class TestEhMobile:
    def teardown_method(self):
        _restaurar()

    def test_padrao_e_desktop(self, monkeypatch):
        monkeypatch.delenv("GA_FORCAR_MOBILE", raising=False)
        _restaurar()
        assert armazenamento.eh_mobile() is False

    def test_storage_definido_nao_torna_mobile(self, monkeypatch):
        # O conftest define FLET_APP_STORAGE_DATA (como o desktop empacotado).
        monkeypatch.delenv("GA_FORCAR_MOBILE", raising=False)
        _restaurar()
        assert armazenamento._STORAGE is not None
        armazenamento.definir_layout_mobile(False)
        assert armazenamento.eh_mobile() is False

    def test_plataforma_mobile(self, monkeypatch):
        monkeypatch.delenv("GA_FORCAR_MOBILE", raising=False)
        armazenamento.definir_layout_mobile(True)
        assert armazenamento.eh_mobile() is True

    def test_variavel_forca_layout_de_celular(self, monkeypatch):
        monkeypatch.setenv("GA_FORCAR_MOBILE", "1")
        armazenamento.definir_layout_mobile(False)
        assert armazenamento.eh_mobile() is True


def test_eh_mobile_responde_antes_de_definir_layout():
    """Quem chamar eh_mobile() sem passar pelo main recebe False, não NameError.

    O layout só é definido em main(), quando o Flet informa a plataforma. Um
    teste ou script que importe o módulo e pergunte antes disso precisa de uma
    resposta utilizável.
    """
    import importlib

    import armazenamento

    recarregado = importlib.reload(armazenamento)
    try:
        assert recarregado.eh_mobile() is False
    finally:
        recarregado.definir_layout_mobile(False)
