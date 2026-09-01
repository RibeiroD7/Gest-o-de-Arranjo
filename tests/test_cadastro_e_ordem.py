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


class TestArrastarNoMes:
    """Arrastar uma linha do mês: as datas ficam paradas, as pessoas andam."""

    def _arranjo_com_oradores(self, datas=("07/11/2026", "14/11/2026", "21/11/2026")):
        conn = database.get_connection()
        try:
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Alfa')")
            cong = conn.execute("SELECT id FROM congregacoes WHERE nome = 'Alfa'").fetchone()[0]
            for nome in ("Um", "Dois", "Três"):
                conn.execute(
                    "INSERT INTO oradores (nome, categoria, congregacao_id) "
                    "VALUES (?, 'Ancião', ?)",
                    (nome, cong),
                )
            conn.execute(
                "INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 11, 11)"
            )
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            ids = {nome: oid for oid, nome in conn.execute("SELECT id, nome FROM oradores")}
            for nome, data in zip(("Um", "Dois", "Três"), datas):
                conn.execute(
                    "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, data) "
                    "VALUES (?, 'recebido', ?, ?)",
                    (arranjo, ids[nome], data),
                )
            conn.commit()
        finally:
            conn.close()
        return arranjo

    def _por_data(self, arranjo_id):
        return {
            r["data"]: r["orador_nome"]
            for r in database.carregar_oradores_arranjo(arranjo_id)
        }

    def test_a_conta_de_para_onde_cada_um_vai(self):
        assert main._ordem_apos_arrastar(4, 3, 0) == [3, 0, 1, 2]
        assert main._ordem_apos_arrastar(4, 0, 3) == [1, 2, 3, 0]
        assert main._ordem_apos_arrastar(4, 1, 2) == [0, 2, 1, 3]

    def test_indice_fora_da_lista_nao_bagunca(self):
        assert main._ordem_apos_arrastar(3, 9, 0) == [0, 1, 2]
        assert main._ordem_apos_arrastar(3, 0, 9) == [1, 2, 0]

    def test_o_ultimo_arrastado_para_cima_assume_a_primeira_data(self):
        arranjo = self._arranjo_com_oradores()
        registros = database.carregar_oradores_arranjo(arranjo)
        ordem = main._ordem_apos_arrastar(3, 2, 0)

        main.aplicar_ordem_designacoes(
            registros, [int(registros[i]["id"]) for i in ordem]
        )

        assert self._por_data(arranjo) == {
            "07/11/2026": "Três", "14/11/2026": "Um", "21/11/2026": "Dois",
        }

    def test_as_datas_do_mes_continuam_as_mesmas(self):
        arranjo = self._arranjo_com_oradores()
        registros = database.carregar_oradores_arranjo(arranjo)
        ordem = main._ordem_apos_arrastar(3, 0, 2)

        main.aplicar_ordem_designacoes(
            registros, [int(registros[i]["id"]) for i in ordem]
        )

        assert sorted(self._por_data(arranjo)) == [
            "07/11/2026", "14/11/2026", "21/11/2026"
        ]

    def test_o_mesmo_orador_em_duas_datas_nao_quebra_a_troca(self):
        """O índice único (arranjo, tipo, orador, data) barrava o meio do caminho."""
        arranjo = self._arranjo_com_oradores()
        conn = database.get_connection()
        try:
            um = conn.execute("SELECT id FROM oradores WHERE nome = 'Um'").fetchone()[0]
            conn.execute(
                "UPDATE arranjo_oradores SET orador_id = ? WHERE data = '21/11/2026'",
                (um,),
            )
            conn.commit()
        finally:
            conn.close()
        registros = database.carregar_oradores_arranjo(arranjo)
        ordem = main._ordem_apos_arrastar(3, 2, 0)

        main.aplicar_ordem_designacoes(
            registros, [int(registros[i]["id"]) for i in ordem]
        )

        assert sorted(self._por_data(arranjo)) == [
            "07/11/2026", "14/11/2026", "21/11/2026"
        ]

    def test_a_tabela_do_mes_vira_lista_arrastavel(self):
        arranjo = self._arranjo_com_oradores()
        registros = database.carregar_oradores_arranjo(arranjo)
        controles = main._montar_tabela_secao(
            registros, "vazio", lambda i: None, lambda i: None,
            on_reordenar=lambda ids: None,
        )
        assert any(
            isinstance(c, flet.ReorderableListView)
            for c in _controles(controles[0])
        )

    def test_sem_data_a_tabela_fica_como_era(self):
        """Sem data não há o que trocar: arrastar não faria sentido."""
        arranjo = self._arranjo_com_oradores(datas=("07/11/2026", "14/11/2026", None))
        registros = database.carregar_oradores_arranjo(arranjo)
        controles = main._montar_tabela_secao(
            registros, "vazio", lambda i: None, lambda i: None,
            on_reordenar=lambda ids: None,
        )
        assert not any(
            isinstance(c, flet.ReorderableListView)
            for c in _controles(controles[0])
        )

    def test_arrastar_na_tabela_avisa_a_nova_ordem(self):
        arranjo = self._arranjo_com_oradores()
        registros = database.carregar_oradores_arranjo(arranjo)
        recebido = {}
        controles = main._montar_tabela_secao(
            registros, "vazio", lambda i: None, lambda i: None,
            on_reordenar=lambda ids: recebido.setdefault("ids", ids),
        )
        lista = next(
            c for c in _controles(controles[0])
            if isinstance(c, flet.ReorderableListView)
        )

        lista.on_reorder(types.SimpleNamespace(old_index=2, new_index=0))

        esperado = [int(registros[i]["id"]) for i in (2, 0, 1)]
        assert recebido["ids"] == esperado


class TestOrdemDosPresidentesDoMes:
    def test_cada_um_assume_a_data_da_vez(self):
        primeiro = database.salvar_presidente_cadastro("Primeiro", "Ancião")
        segundo = database.salvar_presidente_cadastro("Segundo", "Ancião")
        datas = ["07/11/2026", "14/11/2026"]
        database.salvar_presidente(datas[0], primeiro)
        database.salvar_presidente(datas[1], segundo)

        main.aplicar_ordem_presidentes(
            datas, [{"presidente_id": segundo}, {"presidente_id": primeiro}]
        )

        por_data = database.carregar_presidentes_por_ano(2026)
        assert por_data[datas[0]]["nome"] == "Segundo"
        assert por_data[datas[1]]["nome"] == "Primeiro"

    def test_o_nome_avulso_anda_junto(self):
        """Quem presidiu sem estar no cadastro não pode virar cadastro na troca."""
        cadastrado = database.salvar_presidente_cadastro("Cadastrado", "Ancião")
        datas = ["07/11/2026", "14/11/2026"]
        database.salvar_presidente(datas[0], cadastrado)
        database.salvar_presidente_avulso(datas[1], "Visitante")

        main.aplicar_ordem_presidentes(
            datas,
            [{"nome": "Visitante", "avulso": True}, {"presidente_id": cadastrado}],
        )

        por_data = database.carregar_presidentes_por_ano(2026)
        assert por_data[datas[0]]["nome"] == "Visitante"
        assert por_data[datas[0]]["avulso"] is True
        assert por_data[datas[1]]["nome"] == "Cadastrado"

    def test_semana_que_ficou_sem_ninguem_fica_vazia(self):
        cadastrado = database.salvar_presidente_cadastro("Cadastrado", "Ancião")
        datas = ["07/11/2026", "14/11/2026"]
        database.salvar_presidente(datas[0], cadastrado)

        main.aplicar_ordem_presidentes(datas, [None, {"presidente_id": cadastrado}])

        por_data = database.carregar_presidentes_por_ano(2026)
        assert datas[0] not in por_data
        assert por_data[datas[1]]["nome"] == "Cadastrado"

    def test_a_altura_da_linha_conta_o_nome_que_quebra(self):
        """A lista arrastável precisa de altura fechada; o chute é por linha."""
        curta = main._altura_linha_orador_mes(
            {"orador_nome": "Carlos Soares", "tema_titulo": "46 - Fortaleça sua confiança"}
        )
        comprida = main._altura_linha_orador_mes(
            {"orador_nome": "Tevaldo Antônio da Costa", "tema_titulo": "191 - Como o amor vence"}
        )
        assert comprida > curta
