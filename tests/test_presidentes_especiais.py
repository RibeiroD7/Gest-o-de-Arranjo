"""Aba dos presidentes de datas especiais: a fila, o histórico e o rodízio.

A escala das datas especiais é à parte da semanal, e cada TIPO de evento tem
a sua fila: presidir a Celebração não faz ninguém perder a vez na visita do
superintendente. A aba mostra de quem é a vez em cada uma.
"""

from datetime import date

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import armazenamento  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def anciaos():
    """Três anciãos na escala das datas especiais, num banco limpo."""
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("datas_especiais", "presidentes", "presidentes_cadastro"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.commit()
    finally:
        conn.close()
    return {
        nome: database.salvar_presidente_cadastro(nome, "Ancião", preside_especiais=True)
        for nome in ("Ancião A", "Ancião B", "Ancião C")
    }


class TestFilaDoTipo:
    def test_quem_nunca_fez_vem_antes_de_quem_fez(self, anciaos):
        database.salvar_data_especial("11/04/2026", "Celebração", "", "", anciaos["Ancião A"])
        historico = database.historico_presidentes_por_tipo_de_evento()
        geral = {d: p for datas in historico.values() for d, p in datas.items()}
        elegiveis = database.listar_presidentes_cadastro(escala="especiais")

        fila = main._fila_do_tipo("Celebração", elegiveis, historico, geral)
        assert fila[-1] == anciaos["Ancião A"], "quem acabou de presidir vai para o fim"

    def test_a_fila_de_um_tipo_nao_mexe_na_do_outro(self, anciaos):
        """É a regra central: cada evento tem a sua vez."""
        database.salvar_data_especial("11/04/2026", "Celebração", "", "", anciaos["Ancião A"])
        database.salvar_data_especial(
            "14/05/2026", "Visita do Superintendente", "", "", anciaos["Ancião B"]
        )
        historico = database.historico_presidentes_por_tipo_de_evento()
        geral = {d: p for datas in historico.values() for d, p in datas.items()}
        elegiveis = database.listar_presidentes_cadastro(escala="especiais")

        celebracao = main._fila_do_tipo("Celebração", elegiveis, historico, geral)
        visita = main._fila_do_tipo("Visita do Superintendente", elegiveis, historico, geral)
        assert celebracao[-1] == anciaos["Ancião A"]
        assert visita[-1] == anciaos["Ancião B"]

    def test_todo_mundo_aparece_na_fila(self, anciaos):
        elegiveis = database.listar_presidentes_cadastro(escala="especiais")
        fila = main._fila_do_tipo("Celebração", elegiveis, {}, {})
        assert sorted(fila) == sorted(anciaos.values())

    def test_sem_ninguem_marcado_a_fila_e_vazia(self):
        assert main._fila_do_tipo("Celebração", [], {}, {}) == []


class TestUltimaVezNoTipo:
    def test_pega_a_data_mais_recente(self):
        historico = {"11/04/2024": 7, "02/04/2026": 7, "05/12/2025": 9}
        assert main._ultima_vez_no_tipo(7, historico) == "02/04/2026"

    def test_ordena_por_calendario_e_nao_por_texto(self):
        """05/12 é depois de 11/04, mas como texto viria antes."""
        historico = {"11/04/2026": 3, "05/12/2026": 3}
        assert main._ultima_vez_no_tipo(3, historico) == "05/12/2026"

    def test_quem_nunca_presidiu_volta_vazio(self):
        assert main._ultima_vez_no_tipo(99, {"11/04/2026": 7}) == ""


class TestRodizioDasPendentes:
    def test_preenche_o_ano_inteiro_sem_tocar_no_passado(self, anciaos):
        """Preencher por rodízio uma data que já passou é inventar histórico."""
        database.salvar_data_especial("13/02/2026", "Discurso Especial", "", "", None)
        database.salvar_data_especial("14/11/2026", "Visita do Superintendente", "", "", None)

        preenchidas = main.preencher_presidentes_especiais_rodizio(
            2026, a_partir_de=date(2026, 6, 1)
        )

        assert preenchidas == 1
        especiais = database.listar_datas_especiais_por_ano(2026)
        assert not especiais["13/02/2026"]["presidente_nome"], "a de fevereiro já passou"
        assert especiais["14/11/2026"]["presidente_nome"]

    def test_assembleia_nao_gasta_a_vez_de_ninguem(self, anciaos):
        database.salvar_data_especial("24/01/2027", "Assembleia de Circuito", "", "", None)
        preenchidas = main.preencher_presidentes_especiais_rodizio(2027, a_partir_de=date(2026, 1, 1))
        assert preenchidas == 0


class TestSecaoNaTela:
    @pytest.mark.parametrize("mobile", [False, True])
    def test_a_aba_monta_com_dados(self, anciaos, mobile):
        import types

        armazenamento.definir_layout_mobile(mobile)
        try:
            database.salvar_data_especial("11/04/2026", "Celebração", "", "", anciaos["Ancião A"])
            database.salvar_data_especial("13/02/2099", "Discurso Especial", "", "", None)
            page = types.SimpleNamespace(
                update=lambda *a, **k: None, width=1200,
                window=types.SimpleNamespace(width=1200, height=800),
                show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
                run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
                on_keyboard_event=None, title="",
            )
            secao = main._secao_presidentes_especiais(page, lambda: None)
            textos = []

            def varrer(no):
                if isinstance(no, flet.Text) and no.value:
                    textos.append(no.value)
                for atributo in ("content", "controls"):
                    valor = getattr(no, atributo, None)
                    if isinstance(valor, list):
                        for filho in valor:
                            varrer(filho)
                    elif valor is not None and not isinstance(valor, str):
                        varrer(valor)

            varrer(secao)
            assert "Celebração" in textos
            assert any("última: 11/04/2026" in t for t in textos), "o histórico aparece"
            assert any("sem presidente" in t for t in textos), "a pendente é cobrada"
        finally:
            armazenamento.definir_layout_mobile(False)

    def test_sem_ninguem_marcado_a_aba_explica_o_que_fazer(self):
        import types

        conn = database.get_connection()
        try:
            # As datas especiais apontam para o cadastro: solta primeiro.
            conn.execute("DELETE FROM datas_especiais")
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()
        page = types.SimpleNamespace(
            update=lambda *a, **k: None, width=1200,
            window=types.SimpleNamespace(width=1200, height=800),
            show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
            run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
            on_keyboard_event=None, title="",
        )
        assert main._secao_presidentes_especiais(page, lambda: None) is not None
