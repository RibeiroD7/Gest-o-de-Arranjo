"""Simpósio: um discurso dividido entre dois oradores da congregação.

Antes virava DUAS linhas no mês, com data e tema repetidos — na tela, no PNG
do quadro e no relatório. Agora é uma linha só, com os dois nomes juntos: é um
compromisso só (uma data, um tema, uma confirmação).
"""

import pytest

import database
from database import create_tables, get_connection
from util import nome_oradores

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # `main` chama ft.run() ao ser importado


def _preparar():
    conn = get_connection()
    try:
        create_tables(conn)
        conn.execute("DELETE FROM arranjo_oradores")
        conn.execute("DELETE FROM arranjos")
        # orador_temas aponta para oradores: apagar na ordem das dependências.
        conn.execute("DELETE FROM orador_temas")
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('Minha')")
        cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) "
            "VALUES ('Eduardo Nunes', 'Ancião', ?), ('Danilo Reis', 'Ancião', ?)",
            (cong, cong),
        )
        conn.execute("INSERT OR REPLACE INTO temas (nr, titulo) VALUES (176, 'Paz e segurança')")
        conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 5, 5)")
        conn.commit()
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        ids = {
            nome: oid
            for oid, nome in conn.execute("SELECT id, nome FROM oradores")
        }
    finally:
        conn.close()
    return arranjo, ids, cong


class TestGravacao:
    def test_grava_os_dois_oradores_numa_linha_so(self):
        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )

        registros = database.carregar_oradores_arranjo(arranjo)
        assert len(registros) == 1, "simpósio não pode virar duas linhas"
        (registro,) = registros
        assert registro["orador_nome"] == "Eduardo Nunes"
        assert registro["orador_2_nome"] == "Danilo Reis"
        assert registro["orador_2_id"] == ids["Danilo Reis"]

    def test_discurso_comum_continua_sem_segundo_orador(self):
        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026"
        )

        (registro,) = database.carregar_oradores_arranjo(arranjo)
        assert registro["orador_2_id"] is None
        assert registro["orador_2_nome"] == ""

    def test_editar_transforma_em_simposio_e_de_volta(self):
        arranjo, ids, cong = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026"
        )
        (registro,) = database.carregar_oradores_arranjo(arranjo)

        database.atualizar_orador_arranjo(
            registro["id"], 176, cong, "03/05/2026", ids["Danilo Reis"]
        )
        (virou,) = database.carregar_oradores_arranjo(arranjo)
        assert virou["orador_2_nome"] == "Danilo Reis"

        database.atualizar_orador_arranjo(registro["id"], 176, cong, "03/05/2026", None)
        (voltou,) = database.carregar_oradores_arranjo(arranjo)
        assert voltou["orador_2_id"] is None

    def test_o_tema_conta_uma_vez_so_no_catalogo(self):
        """Dois oradores, um discurso: o tema não pode contar em dobro."""
        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )

        conn = get_connection()
        try:
            usos = conn.execute(
                "SELECT data_uso FROM tema_uso_por_ano WHERE tema_nr = 176"
            ).fetchall()
        finally:
            conn.close()
        assert usos == [("05/2026",)]


class TestExibicao:
    @pytest.mark.parametrize(
        "registro, esperado",
        [
            ({"orador_nome": "Eduardo", "orador_2_nome": "Danilo"}, "Eduardo/Danilo"),
            ({"orador_nome": "Eduardo", "orador_2_nome": ""}, "Eduardo"),
            ({"orador_nome": "Eduardo"}, "Eduardo"),
            ({"orador_nome": "", "orador_2_nome": "Danilo"}, "Danilo"),
            ({}, ""),
            ({"orador_nome": "  Eduardo  ", "orador_2_nome": " Danilo "}, "Eduardo/Danilo"),
        ],
    )
    def test_nome_junta_os_dois(self, registro, esperado):
        assert nome_oradores(registro) == esperado


class TestRelatorio:
    def test_sai_numa_linha_com_os_dois_nomes(self):
        import relatorios

        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )

        secoes = relatorios.secoes_programacao(2026)
        linhas = [li for s in secoes for li in s["linhas"] if li and li[0] == "03/05"]
        assert len(linhas) == 1, "o relatório não pode repetir a data"
        assert linhas[0][1] == "Eduardo Nunes/Danilo Reis"


class TestQuadroDeAnuncios:
    """O quadro é o que vai para a parede: o simpósio precisa sair inteiro."""

    def _com_simposio(self):
        arranjo, ids, _ = _preparar()
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE configuracoes SET dia_reuniao = 'Sábado', nome_congregacao = 'Minha' "
                "WHERE id = 1"
            )
            conn.commit()
        finally:
            conn.close()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="02/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )
        return ids

    def test_os_dois_nomes_saem_separados_por_barra(self):
        import pdf_quadro

        self._com_simposio()
        linhas = pdf_quadro.carregar_dados_mes(2026, 5)
        do_dia = [li for li in linhas if li["data"].strftime("%d/%m/%Y") == "02/05/2026"]
        assert do_dia, "a data do simpósio não apareceu no quadro"
        assert do_dia[0]["orador"] == "Eduardo Nunes/Danilo Reis"

    def test_formato_antigo_com_duas_linhas_ainda_junta(self):
        """Arranjos cadastrados antes do campo continuam com dois registros."""
        import pdf_quadro

        arranjo, ids, _ = _preparar()
        conn = get_connection()
        try:
            conn.execute("UPDATE configuracoes SET dia_reuniao = 'Sábado' WHERE id = 1")
            conn.commit()
        finally:
            conn.close()
        for nome in ("Eduardo Nunes", "Danilo Reis"):
            database.adicionar_orador_arranjo(
                arranjo, "recebido", ids[nome], 176, data="02/05/2026"
            )

        linhas = pdf_quadro.carregar_dados_mes(2026, 5)
        do_dia = [li for li in linhas if li["data"].strftime("%d/%m/%Y") == "02/05/2026"]
        assert "/" in do_dia[0]["orador"]
        assert set(do_dia[0]["orador"].split("/")) == {"Eduardo Nunes", "Danilo Reis"}


class TestAprovacaoParaDiscursoFora:
    """Quem faz só o discurso local não pode ser oferecido num envio."""

    def _cadastrar(self, aprovado_fora):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        finally:
            conn.close()
        return database.salvar_orador(
            "Só Local", "", "Ancião", cong, "", set(), aprovado_fora=aprovado_fora
        ), cong

    def test_padrao_e_aprovado(self):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            oid = conn.execute("SELECT id FROM oradores LIMIT 1").fetchone()[0]
            aprovado = conn.execute(
                "SELECT COALESCE(aprovado_fora, 1) FROM oradores WHERE id = ?", (oid,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert aprovado == 1, "quem já existia continua podendo ser enviado"
        assert cong

    def test_salvar_e_reler_a_marcacao(self):
        import main

        oid, _ = self._cadastrar(False)
        assert main.carregar_orador(oid)["aprovado_fora"] is False

    def test_continua_no_seletor_do_arranjo(self):
        """No arranjo do mês ele entra igual aos outros — a trava é o PDF."""
        import main

        oid, cong = self._cadastrar(False)
        database.salvar_orador("Vai Fora", "", "Ancião", cong, "", set())

        def nomes(**kwargs):
            return [
                (o.text or "").split(" — ")[0]
                for o in main.carregar_oradores_com_congregacao_opcoes(cong, **kwargs)
            ]

        assert "Só Local" in nomes()
        assert "Vai Fora" in nomes()
        assert "Só Local" in nomes(por_fila=True)
        assert oid

    def test_fica_de_fora_da_lista_de_envio(self):
        """A trava vive na lista de oradores oferecida a outra congregação."""
        import main

        oid, cong = self._cadastrar(False)
        outro = database.salvar_orador("Vai Fora", "", "Ancião", cong, "", set())

        assert main.somente_discurso_local([oid, outro]) == {oid}

    def test_editar_volta_a_aprovar(self):
        oid, cong = self._cadastrar(False)
        database.salvar_orador(
            "Só Local", "", "Ancião", cong, "", set(), orador_id=oid, aprovado_fora=True
        )
        conn = get_connection()
        try:
            valor = conn.execute(
                "SELECT aprovado_fora FROM oradores WHERE id = ?", (oid,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert valor == 1


class TestFilaNaTelaDeOradores:
    """A escolha de quem enviar é feita na tela de Oradores, marcando gente.

    Por isso a ordem "há mais tempo sem discursar" e a data do último envio
    precisam estar ali — sem elas, escolher exige abrir outra tela.
    """

    def _com_historico(self):
        arranjo, ids, cong = _preparar()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) "
                "VALUES ('Nunca Foi', 'Ancião', ?)",
                (cong,),
            )
            conn.commit()
            ids["Nunca Foi"] = conn.execute(
                "SELECT id FROM oradores WHERE nome = 'Nunca Foi'"
            ).fetchone()[0]
        finally:
            conn.close()
        # Eduardo saiu há mais tempo que Danilo.
        database.adicionar_orador_arranjo(
            arranjo, "enviado", ids["Eduardo Nunes"], 176, data="05/01/2026"
        )
        database.adicionar_orador_arranjo(
            arranjo, "enviado", ids["Danilo Reis"], 176, data="05/06/2026"
        )
        return ids

    def test_quem_nunca_saiu_vem_primeiro(self):
        from servicos import oradores_mais_tempo_sem_discurso

        ids = self._com_historico()
        ultima = database.ultima_data_discurso_por_orador()
        ordem = oradores_mais_tempo_sem_discurso(
            [ids["Danilo Reis"], ids["Eduardo Nunes"], ids["Nunca Foi"]], ultima
        )
        assert ordem == [ids["Nunca Foi"], ids["Eduardo Nunes"], ids["Danilo Reis"]]

    def test_rotulo_do_ultimo_envio(self):
        import main

        ids = self._com_historico()
        ultima = database.ultima_data_discurso_por_orador()
        assert main._rotulo_ultima_saida(ultima, ids["Eduardo Nunes"]) == (
            "último envio: 05/01/2026"
        )
        assert main._rotulo_ultima_saida(ultima, ids["Nunca Foi"]) == "nunca foi enviado"
        # Sem dados nenhum (outras congregações) a linha não mostra nada.
        assert main._rotulo_ultima_saida({}, ids["Eduardo Nunes"]) == ""


class TestSoLocalNaoEntraNoEnvio:
    """O PDF de envio oferece oradores a outra congregação.

    Quem faz apenas o discurso local não pode ir nessa lista: o checkbox fica
    travado e, como a marcação pode ter sido feita antes de o cadastro mudar,
    a geração do PDF também descarta.
    """

    def _dois(self):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        finally:
            conn.close()
        vai = database.salvar_orador("Vai Fora", "", "Ancião", cong, "", set())
        fica = database.salvar_orador(
            "Só Local", "", "Ancião", cong, "", set(), aprovado_fora=False
        )
        return vai, fica

    def test_identifica_quem_e_so_local(self):
        import main

        vai, fica = self._dois()
        assert main.somente_discurso_local([vai, fica]) == {fica}
        assert main.somente_discurso_local([vai]) == set()
        assert main.somente_discurso_local([]) == set()

    def test_a_lista_trava_o_checkbox_e_desmarca(self):
        import main
        from tabela import Tabela

        vai, fica = self._dois()
        selecao = {"ids": {vai, fica}}
        colunas = ["id", "nome", "categoria", "telefone", "observacoes", "temas",
                   "aprovado_fora"]
        tabela = Tabela(
            [
                dict(zip(colunas, (vai, "Vai Fora", "Ancião", "", "", "", 1))),
                dict(zip(colunas, (fica, "Só Local", "Ancião", "", "", "", 0))),
            ],
            colunas,
        )
        nada = lambda *a, **k: None  # noqa: E731

        assert main._criar_lista_oradores(tabela, selecao, nada, nada) is not None
        assert fica not in selecao["ids"], "o só local sai da seleção"
        assert vai in selecao["ids"], "o aprovado continua marcado"


class TestNomeRepetidoNaoDerrubaOApp:
    """Nome repetido na mesma congregação tem índice único no banco.

    O diálogo de orador chamava salvar_orador sem tratar o erro, então o
    IntegrityError subia até o Flet e o app inteiro caía com uma tela
    vermelha. O formulário precisa avisar e continuar aberto.
    """

    def _cong(self):
        _preparar()
        conn = get_connection()
        try:
            return conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        finally:
            conn.close()

    def test_o_banco_recusa_o_nome_repetido(self):
        import sqlite3

        cong = self._cong()
        database.salvar_orador("Repetido", "", "Ancião", cong, "", set())
        with pytest.raises(sqlite3.IntegrityError):
            database.salvar_orador("Repetido", "", "Ancião", cong, "", set())

    def test_mesmo_nome_em_outra_congregacao_pode(self):
        cong = self._cong()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Outra')")
            conn.commit()
            outra = conn.execute(
                "SELECT id FROM congregacoes WHERE nome = 'Outra'"
            ).fetchone()[0]
        finally:
            conn.close()
        database.salvar_orador("Xará", "", "Ancião", cong, "", set())
        database.salvar_orador("Xará", "", "Ancião", outra, "", set())  # não levanta

    def test_o_dialogo_avisa_em_vez_de_estourar(self, monkeypatch):
        import main

        cong = self._cong()
        database.salvar_orador("Repetido", "", "Ancião", cong, "", set())

        dialogos = []
        page = _page_falsa(dialogos)
        main.abrir_dialog_orador(page, lambda: None)
        dialog = dialogos[-1]

        campos = _campos_do_dialog(dialog)
        campos["nome"].value = "Repetido"
        campos["congregacao"].value = str(cong)
        # O salvar do formulário é o on_submit do campo de nome.
        campos["nome"].on_submit(None)

        erros = [
            c for c in _todos_os_controles(dialog)
            if isinstance(c, __import__("flet").Text)
            and c.visible and "Já existe um orador" in (c.value or "")
        ]
        assert erros, "o formulário deveria mostrar o aviso de nome repetido"


def _page_falsa(dialogos):
    import types

    import flet

    return types.SimpleNamespace(
        update=lambda *a, **k: None,
        width=1200,
        window=types.SimpleNamespace(width=1200, height=800),
        show_dialog=lambda d: dialogos.append(d),
        pop_dialog=lambda *a, **k: None,
        run_task=lambda *a, **k: None,
        platform=flet.PagePlatform.WINDOWS,
        on_keyboard_event=None,
        title="",
    )


def _todos_os_controles(no, vistos=None):
    vistos = vistos if vistos is not None else []
    if no in vistos:
        return vistos
    vistos.append(no)
    for atributo in ("content", "controls", "actions", "title"):
        filho = getattr(no, atributo, None)
        if isinstance(filho, list):
            for item in filho:
                _todos_os_controles(item, vistos)
        elif filho is not None and hasattr(filho, "__dict__"):
            _todos_os_controles(filho, vistos)
    return vistos


def _campos_do_dialog(dialog):
    import flet

    campos = {}
    for controle in _todos_os_controles(dialog):
        rotulo = (getattr(controle, "label", "") or "").lower()
        if isinstance(controle, flet.TextField) and rotulo == "nome":
            campos["nome"] = controle
        elif isinstance(controle, flet.Dropdown) and rotulo == "congregação":
            campos["congregacao"] = controle
    return campos


class TestArquivadoNaoSeguraONome:
    """Excluir um orador com histórico arquiva (ativo=0) em vez de apagar.

    O índice único pegava todas as linhas, então esse arquivado — que não
    aparece em lugar nenhum da tela — segurava o nome para sempre: recadastrar
    a pessoa, ou renomear outra para aquele nome, batia num "já existe"
    apontando para um registro invisível.
    """

    def _cong(self):
        _preparar()
        conn = get_connection()
        try:
            return conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        finally:
            conn.close()

    def _arquivar(self, orador_id):
        conn = get_connection()
        try:
            conn.execute("UPDATE oradores SET ativo = 0 WHERE id = ?", (orador_id,))
            conn.commit()
        finally:
            conn.close()

    def test_da_para_reusar_o_nome_de_um_arquivado(self):
        cong = self._cong()
        antigo = database.salvar_orador("Fulano", "", "Ancião", cong, "", set())
        self._arquivar(antigo)

        novo = database.salvar_orador("Fulano", "", "Ancião", cong, "", set())
        assert novo != antigo, "o arquivado continua guardado, com o histórico dele"

    def test_da_para_renomear_alguem_para_o_nome_de_um_arquivado(self):
        """O caso relatado: renomear um ativo para o nome de um arquivado."""
        cong = self._cong()
        antigo = database.salvar_orador("Henrique Dias", "", "Ancião", cong, "", set())
        self._arquivar(antigo)
        outro = database.salvar_orador(
            "Gustavo Prado Junior", "", "Ancião", cong, "", set()
        )

        database.salvar_orador(
            "Henrique Dias", "", "Ancião", cong, "", set(), orador_id=outro
        )

        conn = get_connection()
        try:
            nome = conn.execute(
                "SELECT nome FROM oradores WHERE id = ?", (outro,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert nome == "Henrique Dias"

    def test_dois_ativos_com_o_mesmo_nome_continuam_barrados(self):
        """A regra de verdade não afrouxou: só o arquivado deixou de contar."""
        import sqlite3

        cong = self._cong()
        database.salvar_orador("Xará", "", "Ancião", cong, "", set())
        with pytest.raises(sqlite3.IntegrityError):
            database.salvar_orador("Xará", "", "Ancião", cong, "", set())

    def test_a_migracao_nao_funde_ativo_com_arquivado(self):
        """Fundir os dois juntaria históricos de pessoas talvez diferentes."""
        cong = self._cong()
        antigo = database.salvar_orador("Repetido", "", "Ancião", cong, "", set())
        self._arquivar(antigo)
        novo = database.salvar_orador("Repetido", "", "Ancião", cong, "", set())

        conn = get_connection()
        try:
            database.migrar_oradores(conn)
            restantes = {
                linha[0]
                for linha in conn.execute("SELECT id FROM oradores WHERE nome='Repetido'")
            }
        finally:
            conn.close()
        assert restantes == {antigo, novo}, "os dois têm de sobreviver"


class TestTemasPreparados:
    def test_traz_numero_e_titulo_em_ordem(self):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            conn.execute(
                "INSERT OR REPLACE INTO temas (nr, titulo) VALUES (9, 'Nono'), (2, 'Segundo')"
            )
            conn.commit()
        finally:
            conn.close()
        oid = database.salvar_orador("Com Temas", "", "Ancião", cong, "", {9, 2})

        assert database.carregar_temas_com_titulo_de_orador(oid) == [
            (2, "Segundo"),
            (9, "Nono"),
        ]

    def test_sem_temas_devolve_lista_vazia(self):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        finally:
            conn.close()
        oid = database.salvar_orador("Sem Temas", "", "Ancião", cong, "", set())
        assert database.carregar_temas_com_titulo_de_orador(oid) == []


class TestSimposioAoEnviar:
    """Dois daqui indo juntos a outra congregação também é simpósio."""

    def _dialog(self, tipo: str):
        import main

        arranjo, ids, cong = _preparar()
        main.salvar_configuracao({
            "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
            "coordenador_discursos": "", "telefone_coordenador": "",
            "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
        })
        dialogos = []
        main.abrir_seletor_oradores(
            _page_falsa(dialogos), arranjo, tipo, lambda: None
        )
        return dialogos[0], ids

    def _caixa_simposio(self, dialog):
        return next(
            c for c in _todos_os_controles(dialog)
            if isinstance(c, flet.Checkbox) and "Simpósio" in (c.label or "")
        )

    def _campo_segundo(self, dialog):
        return next(
            c for c in _todos_os_controles(dialog)
            if isinstance(c, flet.Dropdown) and "Segundo orador" in (c.label or "")
        )

    def test_a_opcao_aparece_ao_adicionar_designacao(self):
        dialog, _ = self._dialog("enviado")
        assert self._caixa_simposio(dialog).visible is not False

    def test_a_opcao_continua_ao_adicionar_orador_recebido(self):
        dialog, _ = self._dialog("recebido")
        assert self._caixa_simposio(dialog).visible is not False

    def test_o_segundo_orador_do_envio_e_da_minha_congregacao(self):
        dialog, ids = self._dialog("enviado")
        opcoes = {o.key for o in self._campo_segundo(dialog).options}
        assert opcoes == {str(oid) for oid in ids.values()}

    def test_marcar_a_caixa_mostra_o_campo(self):
        dialog, _ = self._dialog("enviado")
        caixa = self._caixa_simposio(dialog)
        campo = self._campo_segundo(dialog)
        assert not campo.visible
        caixa.value = True
        caixa.on_change(None)
        assert campo.visible

    def test_editar_uma_designacao_enviada_oferece_o_simposio(self):
        import main

        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "enviado", ids["Eduardo Nunes"], 176, data="03/05/2026"
        )
        registro = database.carregar_oradores_arranjo(arranjo)[0]
        dialogos = []
        main.abrir_dialog_editar_orador_arranjo(
            _page_falsa(dialogos), registro, lambda: None
        )

        assert self._caixa_simposio(dialogos[0]).visible is not False
