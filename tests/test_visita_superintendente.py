"""A visita do superintendente: o orador que já vem preenchido e os dois discursos.

Durante a visita o orador é sempre o mesmo — o superintendente de circuito —,
e a reunião tem dois discursos: o público e o final. As duas coisas mudam o
cadastro da data especial e o Quadro de Anúncios.
"""

import sqlite3
import types
from datetime import date

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import armazenamento  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402
from pdf_quadro import carregar_dados_mes  # noqa: E402
from util import eh_visita_superintendente  # noqa: E402

CONFIG_BASE = {
    "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
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
    """Todos os controles da árvore, em profundidade."""
    achados = [raiz]
    for atributo in ("content", "controls", "actions"):
        valor = getattr(raiz, atributo, None)
        if isinstance(valor, list):
            for filho in valor:
                achados += _controles(filho)
        elif valor is not None and not isinstance(valor, str):
            achados += _controles(valor)
    return achados


@pytest.fixture
def banco_limpo():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("datas_especiais", "presidentes", "reuniao_historico"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.commit()
    finally:
        conn.close()
    main.salvar_configuracao(dict(CONFIG_BASE))


class TestQualTipoEAVisita:
    def test_o_nome_do_tipo_padrao(self):
        assert eh_visita_superintendente("Visita do Superintendente")

    def test_variacoes_de_escrita_do_usuario(self):
        assert eh_visita_superintendente("visita do superintendente de circuito")
        assert eh_visita_superintendente("SUPERINTENDENTE DE CIRCUITO")

    def test_os_outros_eventos_ficam_de_fora(self):
        for tipo in ("Celebração", "Assembleia de Circuito", "Arranjo Local", ""):
            assert not eh_visita_superintendente(tipo)


class TestNomeDoSuperintendente:
    def test_fica_guardado_com_os_dados_da_congregacao(self, banco_limpo):
        main.salvar_configuracao({**CONFIG_BASE, "superintendente_circuito": "Wagner Mendes"})
        assert main.carregar_configuracao()["superintendente_circuito"] == "Wagner Mendes"

    def test_quem_salva_sem_o_campo_nao_quebra(self, banco_limpo):
        """Telas antigas (e os testes) chamam o salvar sem a chave nova."""
        main.salvar_configuracao(dict(CONFIG_BASE))
        assert main.carregar_configuracao()["superintendente_circuito"] == ""

    def test_o_campo_esta_na_tela_da_congregacao(self, banco_limpo):
        rotulos = [
            c.label for c in _controles(main.tela_minha_congregacao(_page(), lambda: None))
            if isinstance(c, flet.TextField)
        ]
        assert "Superintendente de circuito" in rotulos


class TestDoisDiscursosNoCadastro:
    def test_o_tema_final_e_gravado_e_lido(self, banco_limpo):
        database.salvar_data_especial(
            "12/09/2026", "Visita do Superintendente", "Wagner Mendes",
            "Tema do público", None, tema_final="Tema do final",
        )
        registro = database.listar_datas_especiais_por_ano(2026)["12/09/2026"]
        assert registro["tema"] == "Tema do público"
        assert registro["tema_final"] == "Tema do final"

    def test_editar_mantem_os_dois_temas_separados(self, banco_limpo):
        database.salvar_data_especial(
            "12/09/2026", "Visita do Superintendente", "Wagner Mendes",
            "Público", None, tema_final="Final",
        )
        registro_id = database.listar_datas_especiais_por_ano(2026)["12/09/2026"]["id"]
        database.salvar_data_especial(
            "12/09/2026", "Visita do Superintendente", "Wagner Mendes",
            "Público", None, registro_id=registro_id, tema_final="Outro final",
        )
        registro = database.listar_datas_especiais_por_ano(2026)["12/09/2026"]
        assert (registro["tema"], registro["tema_final"]) == ("Público", "Outro final")

    def test_data_sem_discurso_final_fica_vazia(self, banco_limpo):
        database.salvar_data_especial("11/04/2026", "Celebração", "", "Tema", None)
        assert database.listar_datas_especiais_por_ano(2026)["11/04/2026"]["tema_final"] == ""


class TestOFormularioDaVisita:
    """Ao escolher a visita, o orador já vem preenchido e sobra um campo."""

    def _abrir(self, tipo_inicial: str):
        page = _page()
        capturado = {}
        page.show_dialog = lambda dialog: capturado.setdefault("dialog", dialog)
        registro = {
            "id": 1, "data": "12/09/2026", "tipo": tipo_inicial, "orador": "",
            "tema": "", "tema_final": "", "presidente_id": None,
            "congregacao_id": None, "presidente_avulso": "",
        }
        main.abrir_dialog_data_especial(page, 2026, 9, lambda: None, registro)
        return capturado["dialog"]

    def _campo(self, dialog, rotulo_comeca_com: str):
        for controle in _controles(dialog):
            if isinstance(controle, flet.TextField) and (controle.label or "").startswith(
                rotulo_comeca_com
            ):
                return controle
        return None

    def test_o_orador_vem_preenchido_com_o_superintendente(self, banco_limpo):
        main.salvar_configuracao({**CONFIG_BASE, "superintendente_circuito": "Wagner Mendes"})
        dialog = self._abrir("Visita do Superintendente")
        assert self._campo(dialog, "Orador").value == "Wagner Mendes"

    def test_o_campo_do_discurso_final_aparece_na_visita(self, banco_limpo):
        dialog = self._abrir("Visita do Superintendente")
        assert self._campo(dialog, "Tema do discurso final").visible

    def test_o_campo_da_congregacao_some_na_visita(self, banco_limpo):
        dialog = self._abrir("Visita do Superintendente")
        congregacao = [
            c for c in _controles(dialog)
            if isinstance(c, flet.Dropdown) and (c.label or "").startswith("Congregação")
        ]
        assert congregacao and not congregacao[0].visible

    def test_nos_outros_eventos_nada_disso_aparece(self, banco_limpo):
        main.salvar_configuracao({**CONFIG_BASE, "superintendente_circuito": "Wagner Mendes"})
        dialog = self._abrir("Celebração")
        assert self._campo(dialog, "Orador").value == ""
        assert not self._campo(dialog, "Tema do discurso final").visible
        assert all(
            c.visible for c in _controles(dialog)
            if isinstance(c, flet.Dropdown) and (c.label or "").startswith("Congregação")
        )

    def test_sem_o_nome_cadastrado_a_tela_diz_onde_cadastrar(self, banco_limpo):
        dialog = self._abrir("Visita do Superintendente")
        avisos = [
            c.value for c in _controles(dialog)
            if isinstance(c, flet.Text) and c.visible and c.value
        ]
        assert any("Minha congregação" in texto for texto in avisos)


class TestOsDoisDiscursosNoQuadro:
    def _visita(self, tema_final: str = "Tema do final"):
        # 12/09/2026 é um sábado, dia de reunião da configuração de teste.
        database.salvar_data_especial(
            "12/09/2026", "Visita do Superintendente", "Wagner Mendes",
            "Tema do público", None, tema_final=tema_final,
        )
        linhas = {li["data"]: li for li in carregar_dados_mes(2026, 9)}
        return linhas[date(2026, 9, 12)]

    def test_o_discurso_final_tem_a_sua_linha(self, banco_limpo):
        assert self._visita()["tema_final"] == "Tema do final"
        assert self._visita()["tema"] == "Tema do público"

    def test_a_visita_sem_tema_anuncia_o_discurso_mesmo_assim(self, banco_limpo):
        """A reunião tem dois discursos; o tema do segundo pode não ter chegado."""
        assert self._visita(tema_final="")["tema_final"] == "—"

    def test_a_congregacao_nao_aparece_na_visita(self, banco_limpo):
        """O superintendente não vem de uma congregação: a linha não existe."""
        assert self._visita()["congregacao"] == ""

    def test_semana_comum_nao_ganha_a_linha(self, banco_limpo):
        linhas = carregar_dados_mes(2026, 9)
        assert all(not linha["tema_final"] for linha in linhas)

    def test_outra_data_especial_nao_ganha_a_linha(self, banco_limpo):
        database.salvar_data_especial("05/09/2026", "Celebração", "", "Tema", None)
        linhas = {li["data"]: li for li in carregar_dados_mes(2026, 9)}
        assert linhas[date(2026, 9, 5)]["tema_final"] == ""
        assert linhas[date(2026, 9, 5)]["congregacao"] == "—", "as outras mantêm a linha"

    def test_o_pdf_do_par_continua_com_uma_pagina_por_mes(self, banco_limpo):
        """A linha extra não pode empurrar o mês de cinco semanas para outra página."""
        pypdf = pytest.importorskip("pypdf")
        # Outubro/2026 tem cinco sábados: é o mês mais cheio possível.
        database.salvar_data_especial(
            "31/10/2026", "Visita do Superintendente", "Wagner Mendes",
            "Tema do público bem comprido para forçar a largura", None,
            tema_final="Tema do discurso final, também comprido",
        )
        from pdf_quadro import gerar_quadro_anuncios

        caminho, erro = gerar_quadro_anuncios(2026, 9)
        assert erro is None
        assert len(pypdf.PdfReader(caminho).pages) == 2


class TestBancoAntigo:
    def test_a_migracao_cria_as_colunas_novas(self, tmp_path):
        """Quem atualiza o app traz um banco sem as colunas da visita."""
        caminho = tmp_path / "antigo.db"
        conn = sqlite3.connect(caminho)
        conn.execute("CREATE TABLE configuracoes (id INTEGER PRIMARY KEY, circuito TEXT)")
        conn.execute("CREATE TABLE datas_especiais (id INTEGER PRIMARY KEY, tema TEXT)")
        conn.commit()

        database._migracao_5_visita_superintendente(conn)

        config = [linha[1] for linha in conn.execute("PRAGMA table_info(configuracoes)")]
        especiais = [linha[1] for linha in conn.execute("PRAGMA table_info(datas_especiais)")]
        assert "superintendente_circuito" in config
        assert "tema_final" in especiais
        conn.close()

    def test_rodar_de_novo_nao_quebra(self, tmp_path):
        caminho = tmp_path / "antigo.db"
        conn = sqlite3.connect(caminho)
        conn.execute("CREATE TABLE configuracoes (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE datas_especiais (id INTEGER PRIMARY KEY)")
        conn.commit()
        database._migracao_5_visita_superintendente(conn)
        database._migracao_5_visita_superintendente(conn)
        conn.close()

    def test_o_esquema_do_app_chegou_na_versao_5(self):
        assert database.ESQUEMA_ATUAL >= 5


class TestTelasQueEstavamEspremidas:
    """Duas telas não cabiam na largura do celular."""

    @pytest.fixture
    def no_celular(self):
        armazenamento.definir_layout_mobile(True)
        yield
        armazenamento.definir_layout_mobile(False)

    def _dialog_tipos(self):
        page = _page()
        capturado = {}
        page.show_dialog = lambda dialog: capturado.setdefault("dialog", dialog)
        main.abrir_dialog_gerenciar_tipos_evento(page, lambda: None)
        return capturado["dialog"]

    def test_o_nome_do_tipo_nao_divide_a_linha_com_as_caixas(self, banco_limpo, no_celular):
        """Numa linha só, o nome era espremido e quebrava letra a letra."""
        database.adicionar_tipo_evento("Arranjo Local")
        linhas_com_nome = [
            c for c in _controles(self._dialog_tipos())
            if isinstance(c, flet.Row)
            and any(
                isinstance(f, flet.Text) and f.value == "Arranjo Local"
                for f in (c.controls or [])
            )
        ]
        assert linhas_com_nome, "o tipo precisa aparecer na lista"
        for linha in linhas_com_nome:
            assert not any(isinstance(f, flet.Checkbox) for f in linha.controls)

    def test_no_computador_continua_tudo_na_mesma_linha(self, banco_limpo):
        database.adicionar_tipo_evento("Arranjo Local")
        linhas = [
            c for c in _controles(self._dialog_tipos())
            if isinstance(c, flet.Row)
            and any(
                isinstance(f, flet.Text) and f.value == "Arranjo Local"
                for f in (c.controls or [])
            )
        ]
        assert any(
            any(isinstance(f, flet.Checkbox) for f in linha.controls) for linha in linhas
        )

    def test_os_valores_da_data_especial_tem_tamanho_proprio(self, banco_limpo, no_celular):
        """Sem isso, com a fonte aumentada, o valor do dropdown saía cortado."""
        page = _page()
        capturado = {}
        page.show_dialog = lambda dialog: capturado.setdefault("dialog", dialog)
        main.abrir_dialog_data_especial(page, 2026, 9, lambda: None)
        dropdowns = [
            c for c in _controles(capturado["dialog"]) if isinstance(c, flet.Dropdown)
        ]
        assert dropdowns
        assert all(d.text_size for d in dropdowns)
