"""Ajustes pedidos nas telas: quadro, faixas de dia e presidentes fora da escala.

São regras pequenas, mas cada uma tem um jeito errado de calcular que passa
despercebido: o bimestre do quadro virando o ano, a faixa de dia que fecha no
mês anterior, e o arquivado que não pode voltar a aparecer sozinho.
"""

import types

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import database  # noqa: E402
import main  # noqa: E402
from util import (  # noqa: E402
    formatar_periodo_reuniao,
    mes_anterior,
    mes_seguinte,
    periodos_de_reuniao,
)


def _page():
    return types.SimpleNamespace(
        update=lambda *a, **k: None, width=1200,
        window=types.SimpleNamespace(width=1200, height=800),
        show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
        run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
        on_keyboard_event=None, title="",
    )


class TestProximoParDoQuadro:
    """O quadro é preparado com antecedência: em agosto, monta-se set-out."""

    def test_agosto_aponta_para_setembro_outubro(self):
        assert main._proximo_par_quadro(2026, 8) == (2026, 9, 10)

    def test_o_primeiro_mes_do_par_da_o_mesmo_resultado(self):
        assert main._proximo_par_quadro(2026, 7) == main._proximo_par_quadro(2026, 8)

    def test_novembro_e_dezembro_viram_o_ano(self):
        assert main._proximo_par_quadro(2026, 11) == (2027, 1, 2)
        assert main._proximo_par_quadro(2026, 12) == (2027, 1, 2)

    def test_janeiro_aponta_para_marco_abril(self):
        assert main._proximo_par_quadro(2026, 1) == (2026, 3, 4)


class TestFaixasDoDiaDaReuniao:
    def test_uma_faixa_fecha_no_mes_anterior_a_seguinte(self):
        periodos = periodos_de_reuniao([
            {"inicio": "2020-05", "dia_semana": "Domingo"},
            {"inicio": "2024-01", "dia_semana": "Sábado"},
        ])
        assert periodos[0]["fim"] == "2023-12"
        assert periodos[1]["fim"] == "", "a última faixa fica em aberto"

    def test_a_ordem_nao_depende_de_como_veio_do_banco(self):
        periodos = periodos_de_reuniao([
            {"inicio": "2024-01", "dia_semana": "Sábado"},
            {"inicio": "2020-05", "dia_semana": "Domingo"},
        ])
        assert [p["inicio"] for p in periodos] == ["2020-05", "2024-01"]

    def test_texto_da_faixa(self):
        assert formatar_periodo_reuniao(
            {"inicio": "2020-05", "fim": "2023-12"}
        ) == "05/2020 até 12/2023"
        assert formatar_periodo_reuniao(
            {"inicio": "2024-01", "fim": ""}
        ) == "01/2024 até hoje"

    def test_virada_de_ano_nos_dois_sentidos(self):
        assert mes_anterior("2024-01") == "2023-12"
        assert mes_seguinte("2023-12") == "2024-01"
        assert mes_anterior("2024-03") == "2024-02"
        assert mes_seguinte("2024-03") == "2024-04"

    def test_texto_estragado_nao_derruba(self):
        assert mes_anterior("") == ""
        assert mes_seguinte("2024") == ""
        assert periodos_de_reuniao([]) == []


class TestPresidentesForaDaEscala:
    @pytest.fixture(autouse=True)
    def _banco_limpo(self):
        conn = database.get_connection()
        try:
            database.create_tables(conn)
            for tabela in ("datas_especiais", "presidentes", "presidentes_cadastro"):
                conn.execute(f"DELETE FROM {tabela}")
            conn.commit()
        finally:
            conn.close()

    def _textos(self, controle):
        achados = []

        def varrer(no):
            if isinstance(no, flet.Text) and no.value:
                achados.append(no.value)
            # O rótulo de um botão vem em `text` ou em `content` como string.
            for atributo in ("text", "content"):
                valor = getattr(no, atributo, None)
                if isinstance(valor, str) and valor:
                    achados.append(valor)
            for atributo in ("content", "controls"):
                valor = getattr(no, atributo, None)
                if isinstance(valor, list):
                    for filho in valor:
                        varrer(filho)
                elif valor is not None and not isinstance(valor, str):
                    varrer(valor)

        varrer(controle)
        return achados

    def test_o_arquivado_nao_aparece_na_lista(self):
        database.salvar_presidente_cadastro("Quem Fica", "Ancião")
        saiu = database.salvar_presidente_cadastro("Quem Saiu", "Ancião")
        database.arquivar_presidente_cadastro(saiu)

        textos = self._textos(main._secao_presidentes(_page(), lambda: None))

        assert "Quem Fica" in textos
        assert "Quem Saiu" not in textos, "arquivado fica escondido"
        assert any("Fora da escala (1)" in t for t in textos), "mas dá para achar"

    def test_sem_arquivados_o_botao_nem_aparece(self):
        database.salvar_presidente_cadastro("Quem Fica", "Ancião")
        textos = self._textos(main._secao_presidentes(_page(), lambda: None))
        assert not any("Fora da escala" in t for t in textos)
