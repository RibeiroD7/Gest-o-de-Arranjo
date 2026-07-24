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
