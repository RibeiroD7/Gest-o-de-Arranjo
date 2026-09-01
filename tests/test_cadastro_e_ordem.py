"""Cadastro do orador e a ordem do rodízio dos presidentes.

Duas coisas que a tela precisa acertar: a marca de "aprovado para discursar
fora" só faz sentido para orador da minha congregação, e mudar a ordem do
rodízio não pode custar um clique por casa andada.
"""

import types

import pytest

flet = pytest.importorskip("flet")

import database  # noqa: E402
import main  # noqa: E402

CONFIG_BASE = {
    "nome_congregacao": "Minha Congregação", "endereco": "", "cidade": "", "cep": "",
    "coordenador_discursos": "", "telefone_coordenador": "",
    "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
}


def _page():
    return types.SimpleNamespace(
        update=lambda *a, **k: None, width=1200,
        window=types.SimpleNamespace(width=1200, height=800),
        show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
        run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
        on_keyboard_event=None, title="",
    )


def _controles(raiz):
    achados = [raiz]
    for atributo in ("content", "controls", "actions"):
        valor = getattr(raiz, atributo, None)
        if isinstance(valor, list):
            for filho in valor:
                achados += _controles(filho)
        elif valor is not None and not isinstance(valor, str):
            achados += _controles(valor)
    return achados


@pytest.fixture(autouse=True)
def banco_limpo():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("arranjo_oradores", "arranjos", "orador_temas", "oradores",
                       "congregacoes", "presidentes", "presidentes_cadastro"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.commit()
    finally:
        conn.close()
    main.salvar_configuracao(dict(CONFIG_BASE))


def _congregacoes() -> dict[str, int]:
    conn = database.get_connection()
    try:
        for nome in ("Minha Congregação", "Vila Andrade"):
            conn.execute("INSERT OR IGNORE INTO congregacoes (nome) VALUES (?)", (nome,))
        conn.commit()
        return {nome: cid for cid, nome in conn.execute("SELECT id, nome FROM congregacoes")}
    finally:
        conn.close()


class TestAprovadoParaDiscursarFora:
    """A marca é sobre a lista que EU mando: só vale para orador daqui."""

    def _dialog(self, congregacao_id: int | None = None, orador_id: int | None = None):
        page = _page()
        capturado = {}
        page.show_dialog = lambda dialog: capturado.setdefault("dialog", dialog)
        main.abrir_dialog_orador(
            page, lambda: None, orador_id=orador_id, congregacao_padrao=congregacao_id
        )
        return capturado["dialog"]

    def _caixa(self, dialog):
        for controle in _controles(dialog):
            if isinstance(controle, flet.Checkbox) and "outras congregações" in (
                controle.label or ""
            ):
                return controle
        return None

    def test_some_no_orador_de_outra_congregacao(self):
        congs = _congregacoes()
        assert not self._caixa(self._dialog(congs["Vila Andrade"])).visible

    def test_aparece_no_orador_da_minha_congregacao(self):
        congs = _congregacoes()
        assert self._caixa(self._dialog(congs["Minha Congregação"])).visible

    def test_trocar_a_congregacao_no_formulario_esconde(self):
        congs = _congregacoes()
        dialog = self._dialog(congs["Minha Congregação"])
        campo = next(
            c for c in _controles(dialog)
            if isinstance(c, flet.Dropdown) and (c.label or "") == "Congregação"
        )
        campo.value = str(congs["Vila Andrade"])
        campo.on_select(None)
        assert not self._caixa(dialog).visible

    def test_editar_orador_de_fora_nao_o_marca_como_so_local(self):
        """Salvar sem a caixa à vista não pode gravar o "só local" dos outros."""
        congs = _congregacoes()
        orador_id = database.salvar_orador(
            "Jeferson Coutinho", "", "Ancião", congs["Vila Andrade"], "", set(),
            aprovado_fora=False,
        )
        dialog = self._dialog(orador_id=orador_id)
        salvar = next(
            c for c in _controles(dialog)
            if isinstance(c, flet.FilledButton) and c.content == "Salvar"
        )
        salvar.on_click(None)
        assert main.carregar_orador(orador_id)["aprovado_fora"] is True

    def test_sem_congregacao_definida_a_caixa_continua(self):
        """Sem saber qual é a minha, esconder tiraria a opção de todo mundo."""
        main.salvar_configuracao({**CONFIG_BASE, "nome_congregacao": ""})
        congs = _congregacoes()
        assert self._caixa(self._dialog(congs["Vila Andrade"])).visible


class TestOrdemDoRodizio:
    def _cadastro(self):
        for nome in ("Primeiro", "Segundo", "Terceiro"):
            database.salvar_presidente_cadastro(nome, "Ancião")
        return database.listar_presidentes_cadastro()

    def _dialog(self, cadastro):
        page = _page()
        capturado = {}
        page.show_dialog = lambda dialog: capturado.setdefault("dialog", dialog)
        main.abrir_dialog_reordenar_presidentes(page, cadastro, lambda: None)
        return capturado["dialog"]

    def _lista(self, dialog):
        return next(
            c for c in _controles(dialog) if isinstance(c, flet.ReorderableListView)
        )

    def _nomes(self):
        return [item["nome"] for item in database.listar_presidentes_cadastro()]

    def test_a_lista_abre_na_ordem_do_rodizio(self):
        cadastro = self._cadastro()
        textos = [
            c.value for c in _controles(self._lista(self._dialog(cadastro)))
            if isinstance(c, flet.Text)
        ]
        assert [t for t in textos if t in ("Primeiro", "Segundo", "Terceiro")] == [
            "Primeiro", "Segundo", "Terceiro"
        ]

    def test_arrastar_para_cima_grava_na_hora(self):
        cadastro = self._cadastro()
        lista = self._lista(self._dialog(cadastro))

        lista.on_reorder(types.SimpleNamespace(old_index=2, new_index=0))

        assert self._nomes() == ["Terceiro", "Primeiro", "Segundo"]

    def test_arrastar_para_baixo_grava_na_hora(self):
        cadastro = self._cadastro()
        lista = self._lista(self._dialog(cadastro))

        lista.on_reorder(types.SimpleNamespace(old_index=0, new_index=2))

        assert self._nomes() == ["Segundo", "Terceiro", "Primeiro"]

    def test_a_numeracao_acompanha(self):
        cadastro = self._cadastro()
        lista = self._lista(self._dialog(cadastro))
        lista.on_reorder(types.SimpleNamespace(old_index=2, new_index=0))

        primeira_linha = lista.controls[0]
        textos = [c.value for c in _controles(primeira_linha) if isinstance(c, flet.Text)]
        assert textos[0] == "1" and "Terceiro" in textos

    def test_o_botao_aparece_quando_ha_quem_reordenar(self):
        self._cadastro()
        rotulos = [
            c.content for c in _controles(main._secao_presidentes(_page(), lambda: None))
            if isinstance(c, flet.OutlinedButton)
        ]
        assert "Reordenar" in rotulos

    def test_com_um_presidente_so_nao_ha_o_que_reordenar(self):
        database.salvar_presidente_cadastro("Único", "Ancião")
        rotulos = [
            c.content for c in _controles(main._secao_presidentes(_page(), lambda: None))
            if isinstance(c, flet.OutlinedButton)
        ]
        assert "Reordenar" not in rotulos
