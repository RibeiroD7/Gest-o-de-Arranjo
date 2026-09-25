"""Tema com prazo de uso, excluir pelo formulário e a lixeira no celular.

O tema 109 era "não use a partir de setembro" e passou: o limite ficava só
anotado, nada o conferia. E no celular a lixeira da tabela do mês caía fora
da linha — não havia como tirar o orador da data.
"""

from datetime import date

import pytest

import database
from database import create_tables, get_connection
from util import aviso_tema_fora_do_prazo, limite_uso_tema

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # `main` chama ft.run() ao ser importado

from test_simposio import _page_falsa, _todos_os_controles  # noqa: E402


def _preparar(data_limite=None, notas=None, titulo="O Reino de Deus está próximo"):
    conn = get_connection()
    try:
        create_tables(conn)
        conn.execute("DELETE FROM arranjo_oradores")
        conn.execute("DELETE FROM arranjos")
        conn.execute("DELETE FROM orador_temas")
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.execute("UPDATE temas SET data_limite_uso = NULL, notas = NULL")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('Vila Andrade')")
        cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) "
            "VALUES ('Marcio Rocha', 'Ancião', ?)",
            (cong,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO temas (nr, titulo, data_limite_uso, notas) "
            "VALUES (109, ?, ?, ?)",
            (titulo, data_limite, notas),
        )
        conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 11, 11)")
        conn.commit()
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        orador = conn.execute("SELECT id FROM oradores").fetchone()[0]
    finally:
        conn.close()
    return arranjo, orador, cong


class TestLimiteDoTema:
    def test_campo_proprio_em_iso(self):
        assert limite_uso_tema("2026-09-01") == date(2026, 9, 1)

    def test_campo_proprio_como_se_digita_no_brasil(self):
        assert limite_uso_tema("01/09/2026") == date(2026, 9, 1)
        assert limite_uso_tema("09/2026") == date(2026, 9, 1)

    def test_escrito_no_titulo(self):
        titulo = "O Reino de Deus está próximo (Não use a partir de setembro de 2026)"
        assert limite_uso_tema(None, titulo) == date(2026, 9, 1)

    def test_escrito_nas_observacoes(self):
        assert limite_uso_tema("", "Tema", "Não usar a partir de 01/10/2026") == date(
            2026, 10, 1
        )

    def test_sem_limite(self):
        assert limite_uso_tema(None, "Tema comum", None) is None

    def test_antes_do_limite_passa(self):
        assert aviso_tema_fora_do_prazo(109, date(2026, 9, 1), date(2026, 8, 29)) is None

    def test_no_dia_do_limite_ja_bloqueia(self):
        aviso = aviso_tema_fora_do_prazo(109, date(2026, 9, 1), date(2026, 9, 1))
        assert aviso and "109" in aviso and "01/09/2026" in aviso


def _salvar(dialog):
    next(
        c for c in _todos_os_controles(dialog)
        if isinstance(c, flet.FilledButton) and c.content == "Salvar"
    ).on_click(None)


def _erro(dialog):
    return next(
        c.value for c in _todos_os_controles(dialog)
        if isinstance(c, flet.Text) and c.visible and "tema 109" in (c.value or "")
    )


class TestFormularioBloqueiaTemaVencido:
    def test_editar_para_depois_do_prazo_nao_grava(self):
        import main

        arranjo, orador, cong = _preparar(data_limite="2026-09-01")
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, None, congregacao_id=cong, data="21/11/2026"
        )
        registro = database.carregar_oradores_arranjo(arranjo)[0]
        dialogos = []
        main.abrir_dialog_editar_orador_arranjo(
            _page_falsa(dialogos), registro, lambda: None
        )
        campo_tema = next(
            c for c in _todos_os_controles(dialogos[0])
            if isinstance(c, flet.Dropdown) and c.label == "Tema"
        )
        campo_tema.value = "109"
        _salvar(dialogos[0])

        assert "01/09/2026" in _erro(dialogos[0])
        assert database.carregar_oradores_arranjo(arranjo)[0]["tema_nr"] is None

    def test_limite_so_no_titulo_tambem_bloqueia(self):
        import main

        arranjo, orador, cong = _preparar(
            titulo="O Reino de Deus está próximo (Não use a partir de setembro de 2026)"
        )
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, 109, congregacao_id=cong, data="21/11/2026"
        )
        registro = database.carregar_oradores_arranjo(arranjo)[0]
        dialogos = []
        main.abrir_dialog_editar_orador_arranjo(
            _page_falsa(dialogos), registro, lambda: None
        )
        _salvar(dialogos[0])
        assert _erro(dialogos[0])


class TestAvisoNoInicio:
    def test_designacao_ja_marcada_aparece(self):
        arranjo, orador, cong = _preparar(data_limite="2026-09-01")
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, 109, congregacao_id=cong, data="21/11/2026"
        )
        fora = database.designacoes_com_tema_fora_do_prazo(date(2026, 9, 25))
        assert [(f["tema_nr"], f["data"]) for f in fora] == [(109, "21/11/2026")]

    def test_o_que_ja_passou_nao_cobra(self):
        arranjo, orador, cong = _preparar(data_limite="2026-09-01")
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, 109, congregacao_id=cong, data="21/11/2026"
        )
        assert database.designacoes_com_tema_fora_do_prazo(date(2026, 12, 1)) == []


class TestExcluirPeloFormulario:
    def test_dois_toques_tiram_o_orador_da_data(self):
        import main

        arranjo, orador, cong = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, None, congregacao_id=cong, data="21/11/2026"
        )
        registro = database.carregar_oradores_arranjo(arranjo)[0]
        removidos = []
        dialogos = []
        main.abrir_dialog_editar_orador_arranjo(
            _page_falsa(dialogos), registro, lambda: None, on_excluir=removidos.append
        )
        botao = next(
            c for c in _todos_os_controles(dialogos[0])
            if isinstance(c, flet.TextButton) and c.content == "Excluir"
        )
        botao.on_click(None)
        assert removidos == [], "o primeiro toque só pede confirmação"
        botao.on_click(None)
        assert removidos == [int(registro["id"])]

    def test_sem_callback_o_botao_nao_aparece(self):
        import main

        arranjo, orador, cong = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, None, congregacao_id=cong, data="21/11/2026"
        )
        registro = database.carregar_oradores_arranjo(arranjo)[0]
        dialogos = []
        main.abrir_dialog_editar_orador_arranjo(
            _page_falsa(dialogos), registro, lambda: None
        )
        botao = next(
            c for c in _todos_os_controles(dialogos[0])
            if isinstance(c, flet.TextButton) and c.content == "Excluir"
        )
        assert botao.visible is False

    def test_texto_do_simposio_cabe_no_celular(self):
        import main

        caixa = main._caixa_simposio(False)
        assert len(caixa.label) <= 26


class TestLixeiraNoCelular:
    def test_a_coluna_cabe_todos_os_botoes(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "eh_mobile", lambda: True)
        # Status, WhatsApp, mover, editar e remover: 5 botões de 48 px.
        largura = main._largura_acoes_mes(object(), object(), object())
        assert largura >= 5 * main.LARGURA_BOTAO_ACAO_MOBILE

    def test_no_pc_nada_muda(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "eh_mobile", lambda: False)
        assert main._largura_acoes_mes(None, None, None) == main._tema.LARGURA_COL_ACOES_MES
