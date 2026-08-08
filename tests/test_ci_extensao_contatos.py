"""O passo do CI que tira a extensão de contatos do build de desktop.

Se este script errar, os instaladores de Windows e Linux quebram na hora de
compilar — e só se descobre depois de publicar a tag. Por isso ele é testado
contra o pyproject.toml de verdade do projeto.
"""

import importlib.util
import pathlib
import tomllib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / ".github" / "scripts" / "sem_extensao_contatos.py"


def _carregar_script():
    spec = importlib.util.spec_from_file_location("sem_extensao_contatos", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _pyproject() -> str:
    return (RAIZ / "pyproject.toml").read_text(encoding="utf-8")


class TestLimpar:
    def test_o_pyproject_real_declara_a_extensao(self):
        """Guarda a premissa: sem isso o teste abaixo não provaria nada."""
        dados = tomllib.loads(_pyproject())
        assert "flet-contatos" in dados["project"]["dependencies"]
        assert "flet-contatos" in dados["tool"]["flet"]["dev_packages"]

    def test_remove_tudo_que_aponta_para_a_extensao(self):
        limpo = _carregar_script().limpar(_pyproject())
        assert "flet-contatos" not in limpo
        assert "[tool.flet.dev_packages]" not in limpo
        assert "[tool.uv.sources]" not in limpo

    def test_continua_um_toml_valido(self):
        dados = tomllib.loads(_carregar_script().limpar(_pyproject()))
        assert dados["project"]["name"] == "gestao-arranjo"
        assert "dev_packages" not in dados["tool"]["flet"]

    def test_preserva_o_resto_do_build(self):
        """O que o desktop precisa não pode sair junto."""
        dados = tomllib.loads(_carregar_script().limpar(_pyproject()))
        assert dados["tool"]["flet"]["app"]["path"] == "src"
        assert dados["tool"]["flet"]["build_number"] >= 24
        assert any(
            d.startswith("reportlab") or d == "reportlab"
            for d in dados["project"]["dependencies"]
        )
        # A permissão de contatos fica: quem compila para Android usa o mesmo
        # arquivo, e o desktop simplesmente ignora a seção Android.
        assert dados["tool"]["flet"]["android"]["permission"]

    def test_rodar_duas_vezes_nao_muda_nada(self):
        limpar = _carregar_script().limpar
        uma = limpar(_pyproject())
        assert limpar(uma) == uma
