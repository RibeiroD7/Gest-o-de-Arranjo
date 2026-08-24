"""Teste de ida-e-volta do backup (src/database.py).

Garante que exportar → apagar → restaurar recupera os dados idênticos. O banco
fica numa pasta temporária (ver conftest.py).
"""

import database
from database import (
    create_tables,
    exportar_backup,
    get_connection,
    restaurar_backup,
)


def _resetar_banco():
    """Limpa o banco de teste na ordem das dependências (evita erro de FK)."""
    conn = get_connection()
    try:
        create_tables(conn)
        for tabela in (
            "arranjo_oradores",
            "tema_uso_por_ano",
            "orador_temas",
            "designacoes",
            "arranjos",
            "oradores",
            "congregacoes",
        ):
            conn.execute(f"DELETE FROM {tabela}")  # noqa: S608 — nomes fixos
        conn.commit()
    finally:
        conn.close()


def test_backup_roundtrip():
    _resetar_banco()

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO congregacoes (nome, telefone, dia_semana, horario) "
            "VALUES (?, ?, ?, ?)",
            ("Central", "1199999", "domingo", "09:00"),
        )
        cong_id = conn.execute(
            "SELECT id FROM congregacoes WHERE nome = 'Central'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) VALUES (?, ?, ?)",
            ("Fulano", "Ancião", cong_id),
        )
        conn.commit()
    finally:
        conn.close()

    caminho, contagens = exportar_backup()
    assert contagens["congregacoes"] == 1
    assert contagens["oradores"] == 1

    # Apaga tudo e confirma que sumiu.
    conn = get_connection()
    try:
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM congregacoes").fetchone()[0] == 0
    finally:
        conn.close()

    ok, _mensagem = restaurar_backup(caminho)
    assert ok is True

    # Dados voltaram idênticos.
    conn = get_connection()
    try:
        cong = conn.execute(
            "SELECT nome, telefone, dia_semana, horario FROM congregacoes"
        ).fetchall()
        oradores = conn.execute("SELECT nome, categoria FROM oradores").fetchall()
    finally:
        conn.close()

    assert cong == [("Central", "1199999", "domingo", "09:00")]
    assert oradores == [("Fulano", "Ancião")]


def test_backup_usa_pasta_temporaria():
    # Sanidade: o teste não deve tocar o banco real do projeto.
    assert "ga-testes-" in database.DB_PATH


def test_trocar_datas_designacoes():
    """O swap respeita a UNIQUE(arranjo_id, tipo, orador_id, data)."""
    _resetar_banco()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM arranjo_oradores")
        conn.execute("DELETE FROM arranjos")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('X')")
        cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) "
            "VALUES ('A', 'Ancião', ?), ('B', 'Ancião', ?)",
            (cong, cong),
        )
        ids = [r[0] for r in conn.execute("SELECT id FROM oradores ORDER BY nome")]
        conn.execute(
            "INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 1, 1)"
        )
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        conn.execute(
            "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, data) "
            "VALUES (?, 'enviado', ?, '04/01/2026'), (?, 'enviado', ?, '11/01/2026')",
            (arranjo, ids[0], arranjo, ids[1]),
        )
        conn.commit()
        regs = {
            r[1]: r[0]
            for r in conn.execute("SELECT id, orador_id FROM arranjo_oradores")
        }
    finally:
        conn.close()

    database.trocar_datas_designacoes(regs[ids[0]], regs[ids[1]])

    conn = get_connection()
    try:
        datas = dict(
            conn.execute("SELECT orador_id, data FROM arranjo_oradores").fetchall()
        )
    finally:
        conn.close()
    assert datas[ids[0]] == "11/01/2026"
    assert datas[ids[1]] == "04/01/2026"


class TestUsoDosTemas:
    """Designar um orador RECEBIDO deve preencher o 'Último uso' do tema."""

    def _preparar(self):
        _resetar_banco()
        conn = get_connection()
        try:
            conn.execute("DELETE FROM arranjo_oradores")
            conn.execute("DELETE FROM arranjos")
            conn.execute("DELETE FROM tema_uso_por_ano")
            conn.execute("DELETE FROM temas WHERE nr IN (74, 80)")
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Outra')")
            cong = conn.execute("SELECT id FROM congregacoes WHERE nome='Outra'").fetchone()[0]
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) VALUES ('Zé', 'Ancião', ?)",
                (cong,),
            )
            orador = conn.execute("SELECT id FROM oradores WHERE nome='Zé'").fetchone()[0]
            conn.execute("INSERT INTO temas (nr, titulo) VALUES (74, 'Tema 74'), (80, 'Tema 80')")
            conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 10, 10)")
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        return arranjo, orador

    def _uso(self, tema_nr):
        conn = get_connection()
        try:
            linha = conn.execute(
                "SELECT data_uso FROM tema_uso_por_ano WHERE tema_nr = ?", (tema_nr,)
            ).fetchone()
        finally:
            conn.close()
        return linha[0] if linha else None

    def test_recebido_preenche_a_data_do_tema(self):
        arranjo, orador = self._preparar()
        database.adicionar_orador_arranjo(arranjo, "recebido", orador, 74, data="31/10/2026")
        assert self._uso(74) == "10/2026"

    def test_enviado_nao_conta(self):
        """Enviado = o tema foi apresentado em OUTRA congregação."""
        arranjo, orador = self._preparar()
        database.adicionar_orador_arranjo(arranjo, "enviado", orador, 80, data="31/10/2026")
        assert self._uso(80) is None

    def test_mantem_a_data_mais_recente_do_ano(self):
        arranjo, orador = self._preparar()
        database.adicionar_orador_arranjo(arranjo, "recebido", orador, 74, data="05/03/2026")
        database.adicionar_orador_arranjo(arranjo, "recebido", orador, 74, data="12/09/2026")
        assert self._uso(74) == "09/2026"

    def test_cria_a_coluna_do_ano(self):
        arranjo, orador = self._preparar()
        database.adicionar_orador_arranjo(arranjo, "recebido", orador, 74, data="31/10/2026")
        anos = [a["ano"] for a in database.listar_anos_colunas(apenas_visiveis=False)]
        assert 2026 in anos


class TestTelefoneDoPresidente:
    """O telefone do presidente é o destino da mensagem da presidência."""

    def _limpar(self):
        conn = get_connection()
        try:
            create_tables(conn)
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()

    def test_salva_e_le_o_telefone(self):
        self._limpar()
        database.salvar_presidente_cadastro("Fábio Moreira", "Ancião", telefone="11999998888")
        (item,) = database.listar_presidentes_cadastro()
        assert item["telefone"] == "11999998888"

    def test_edicao_atualiza_o_telefone(self):
        self._limpar()
        pid = database.salvar_presidente_cadastro("Fábio Moreira", "Ancião", telefone="1111")
        database.salvar_presidente_cadastro(
            "Fábio Moreira", "Servo Ministerial", cadastro_id=pid, telefone="2222"
        )
        (item,) = database.listar_presidentes_cadastro()
        assert (item["categoria"], item["telefone"]) == ("Servo Ministerial", "2222")

    def test_cadastro_antigo_sem_telefone_vira_string_vazia(self):
        self._limpar()
        database.salvar_presidente_cadastro("Sem Telefone", "Ancião")
        (item,) = database.listar_presidentes_cadastro()
        assert item["telefone"] == ""


class TestDadosDaMensagemDaPresidencia:
    """A tela inicial monta a mensagem com o que estes dois carregadores trazem."""

    def test_recebido_traz_a_congregacao_do_orador(self):
        _resetar_banco()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Jardim Maria Sampaio')")
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) VALUES (?,?,?)",
                ("Carlos Menezes", "Ancião", cong),
            )
            orador = conn.execute("SELECT id FROM oradores").fetchone()[0]
            conn.execute("INSERT INTO temas (nr, titulo) VALUES (34, 'Ande em integridade')")
            conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026,1,1)")
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, 34, congregacao_id=cong, data="31/01/2026"
        )
        registro = database.carregar_recebidos_por_ano(2026)["31/01/2026"]
        assert registro["congregacao"] == "Jardim Maria Sampaio"
        assert registro["orador"] == "Carlos Menezes"

    def test_presidente_do_ano_traz_o_telefone(self):
        conn = get_connection()
        try:
            create_tables(conn)
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()
        pid = database.salvar_presidente_cadastro(
            "Bruno Vidal", "Ancião", telefone="11999998888"
        )
        database.salvar_presidente("31/01/2026", pid)
        assert database.carregar_presidentes_por_ano(2026)["31/01/2026"]["telefone"] == (
            "11999998888"
        )


class TestRelatorios:
    """Os quadros do PDF de relatórios."""

    def _limpar_presidentes(self):
        conn = get_connection()
        try:
            create_tables(conn)
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()

    def test_presidencias_contam_e_ordenam_por_quem_presidiu_menos(self):
        self._limpar_presidentes()
        muito = database.salvar_presidente_cadastro("Muito", "Ancião")
        pouco = database.salvar_presidente_cadastro("Pouco", "Servo Ministerial")
        database.salvar_presidente_cadastro("Nunca", "Ancião")
        for data in ("03/01/2026", "10/01/2026", "17/01/2026"):
            database.salvar_presidente(data, muito)
        database.salvar_presidente("24/01/2026", pouco)

        linhas = database.relatorio_presidencias()
        assert [(item["nome"], item["quantidade"]) for item in linhas] == [
            ("Nunca", 0),
            ("Pouco", 1),
            ("Muito", 3),
        ]
        assert linhas[2]["ultima_data"] == "17/01/2026"
        assert linhas[0]["ultima_data"] == ""

    def test_presidencias_do_ano_mantem_quem_nao_presidiu(self):
        """O filtro do ano não pode sumir com quem ficou de fora — é a informação."""
        self._limpar_presidentes()
        pid = database.salvar_presidente_cadastro("Só em 2025", "Ancião")
        database.salvar_presidente("06/12/2025", pid)
        linhas = database.relatorio_presidencias(2026)
        assert [(item["nome"], item["quantidade"]) for item in linhas] == [("Só em 2025", 0)]

    def test_conflitos_do_ano_trazem_o_tipo(self):
        """Sem o tipo, o par recebido+enviado do orador local viraria conflito."""
        _resetar_banco()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO oradores (nome, categoria) VALUES ('Fulano','Ancião')")
            orador = conn.execute("SELECT id FROM oradores").fetchone()[0]
            conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026,5,5)")
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        for tipo in ("recebido", "enviado"):
            database.adicionar_orador_arranjo(
                arranjo, tipo, orador, None, data="02/05/2026"
            )
        registros = database.carregar_designacoes_ano(2026)
        assert sorted(r["tipo"] for r in registros) == ["enviado", "recebido"]


class TestRodizioContaDatasEspeciais:
    """Presidir um discurso especial conta no rodízio.

    Caso real: o irmão presidiu o Discurso Especial de 26/09 e o app o
    escolheu de novo em 03/10, a semana seguinte. O histórico do rodízio lia
    só a tabela `presidentes`, e o presidente da data especial mora em
    `datas_especiais` — então ele parecia não presidir havia meses.
    """

    def _preparar(self):
        conn = get_connection()
        try:
            create_tables(conn)
            # datas_especiais aponta para presidentes_cadastro: limpa antes.
            conn.execute("DELETE FROM datas_especiais")
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()
        return {
            nome: database.salvar_presidente_cadastro(nome, "Ancião")
            for nome in ("Lucas", "Paulo", "Eduardo")
        }

    def test_presidente_de_data_especial_entra_no_historico(self):
        ids = self._preparar()
        database.salvar_data_especial(
            "26/09/2026", "Discurso Especial", "", "", ids["Lucas"]
        )
        historico = database.carregar_todas_designacoes_presidente()
        assert historico.get("26/09/2026") == ids["Lucas"]

    def test_quem_presidiu_o_especial_nao_e_o_proximo_do_rodizio(self):
        from servicos import escolher_rodizio_presidentes

        ids = self._preparar()
        # Lucas é o 1º da ordem, mas acabou de presidir o especial de 26/09.
        database.salvar_data_especial(
            "26/09/2026", "Discurso Especial", "", "", ids["Lucas"]
        )
        escolhas = escolher_rodizio_presidentes(
            list(ids.values()),
            ["03/10/2026", "10/10/2026", "24/10/2026"],
            especiais=set(),
            designacoes_existentes=database.carregar_todas_designacoes_presidente(),
        )
        primeiro = dict(escolhas)["03/10/2026"]
        assert primeiro != ids["Lucas"], "não pode repetir logo depois do especial"
        # Ele volta ao rodízio depois dos outros, não some da escala.
        assert ids["Lucas"] in dict(escolhas).values()

    def test_relatorio_conta_a_presidencia_do_especial(self):
        ids = self._preparar()
        database.salvar_presidente("05/09/2026", ids["Lucas"])
        database.salvar_data_especial(
            "26/09/2026", "Discurso Especial", "", "", ids["Lucas"]
        )
        linhas = {item["nome"]: item for item in database.relatorio_presidencias()}
        assert linhas["Lucas"]["quantidade"] == 2
        assert linhas["Lucas"]["ultima_data"] == "26/09/2026"
        assert linhas["Paulo"]["quantidade"] == 0


class TestAnoOcultoNaoApagaHistorico:
    """Ocultar a coluna de um ano some com a COLUNA, não com o uso.

    A sugestão de temas ordena pelo último uso; se ocultar 2024 fizesse os
    temas de 2024 parecerem "nunca feitos", eles voltariam para o topo da fila
    indevidamente.
    """

    def _preparar(self):
        _resetar_banco()
        conn = get_connection()
        try:
            conn.execute("DELETE FROM tema_uso_por_ano")
            conn.execute("DELETE FROM temas_anos_colunas")
            conn.execute("INSERT OR REPLACE INTO temas (nr, titulo) VALUES (7, 'Tema 7')")
            conn.commit()
        finally:
            conn.close()
        database.adicionar_ano_coluna(2025)
        database.adicionar_ano_coluna(2026)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso) "
                "VALUES (7, 2026, '08/2026')"
            )
            conn.commit()
        finally:
            conn.close()

    def _tema7(self):
        df = database.carregar_dataframe_temas()
        return df[df["nr"] == 7].iloc[0]

    def test_com_o_ano_visivel(self):
        self._preparar()
        linha = self._tema7()
        assert linha["ultimo_uso"] == "Ago/2026"
        assert linha["2026"] == "Ago/2026", "a coluna do ano também usa o mês por extenso"
        assert "2026" in database.carregar_dataframe_temas().colunas

    def test_ocultando_o_ano_o_ultimo_uso_permanece(self):
        self._preparar()
        database.definir_visibilidade_ano_coluna(2026, False)
        linha = self._tema7()
        assert linha["ultimo_uso"] == "Ago/2026", "o uso não pode sumir com a coluna"
        assert linha["ultimo_uso_chave"] == "2026-08"
        # A coluna, essa sim, desaparece da tabela.
        assert "2026" not in database.carregar_dataframe_temas().colunas


class TestUsoVaiParaAColunaDoProprioAno:
    """A planilha/S-99 gravava as datas em colunas posicionais.

    Um uso de 04/2025 embaixo de 2023 desaparecia da grade assim que essa
    coluna era ocultada, e o tema parecia nunca feito.
    """

    def _preparar(self, usos):
        _resetar_banco()
        conn = get_connection()
        try:
            conn.execute("DELETE FROM temas_anos_colunas")
            conn.execute(
                "INSERT OR REPLACE INTO temas (nr, titulo) VALUES (30, 'Tema 30')"
            )
            conn.commit()
        finally:
            conn.close()
        for ano in sorted({ano for ano, _ in usos}):
            database.adicionar_ano_coluna(ano)
        conn = get_connection()
        try:
            for ano, data in usos:
                conn.execute(
                    "INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso) "
                    "VALUES (30, ?, ?)",
                    (ano, data),
                )
            conn.commit()
        finally:
            conn.close()

    def _usos(self):
        conn = get_connection()
        try:
            return sorted(
                conn.execute(
                    "SELECT ano_coluna, data_uso FROM tema_uso_por_ano WHERE tema_nr = 30"
                )
            )
        finally:
            conn.close()

    def test_a_data_muda_para_a_coluna_do_seu_ano(self):
        self._preparar([(2023, "04/2025"), (2026, "08/2026")])
        assert database.realocar_uso_para_ano_da_data() == 1
        assert self._usos() == [(2025, "04/2025"), (2026, "08/2026")]

    def test_dois_usos_no_mesmo_ano_ficam_com_o_mais_recente(self):
        self._preparar([(2023, "04/2025"), (2024, "03/2025")])
        database.realocar_uso_para_ano_da_data()
        assert self._usos() == [(2025, "04/2025")]

    def test_a_coluna_do_ano_e_criada_quando_falta(self):
        self._preparar([(2023, "07/2027")])
        database.realocar_uso_para_ano_da_data()
        anos = [item["ano"] for item in database.listar_anos_colunas(apenas_visiveis=False)]
        assert 2027 in anos
        assert self._usos() == [(2027, "07/2027")]

    def test_nada_a_fazer_nao_mexe_no_banco(self):
        self._preparar([(2025, "04/2025"), (2026, "08/2026")])
        assert database.realocar_uso_para_ano_da_data() == 0
        assert self._usos() == [(2025, "04/2025"), (2026, "08/2026")]


class TestTipoEventoTemPresidente:
    """Quais eventos pedem presidente local — é o que o rodízio das especiais lê."""

    def _tipos(self) -> dict:
        return {item["nome"]: item["tem_presidente"] for item in database.listar_tipos_evento()}

    def test_padrao_desliga_quem_nao_tem_reuniao_no_salao(self):
        conn = get_connection()
        try:
            database.create_tables(conn)
        finally:
            conn.close()
        tipos = self._tipos()
        assert tipos["Assembleia de Circuito"] is False
        assert tipos["Congresso Regional"] is False
        assert tipos["Reunião Especial"] is False
        assert tipos["Discurso Especial"] is True
        assert tipos["Visita do Superintendente"] is True

    def test_tipo_novo_nasce_pedindo_presidente(self):
        database.adicionar_tipo_evento("Escola de Pioneiros")
        assert self._tipos()["Escola de Pioneiros"] is True

    def test_tipo_apagado_do_cadastro_ainda_pede_presidente(self):
        """Excluir o tipo não pode fazer a data sumir do rodízio em silêncio."""
        database.adicionar_tipo_evento("Escola de Pioneiros")
        alvo = next(
            item for item in database.listar_tipos_evento()
            if item["nome"] == "Escola de Pioneiros"
        )
        database.excluir_tipo_evento(alvo["id"])
        # Some do cadastro, mas a data já criada continua com esse texto.
        assert "Escola de Pioneiros" not in {
            item["nome"] for item in database.listar_tipos_evento()
        }
        assert "Escola de Pioneiros" not in database.tipos_evento_sem_presidente()

    def test_a_escolha_do_usuario_e_gravada(self):
        alvo = next(
            item for item in database.listar_tipos_evento()
            if item["nome"] == "Assembleia de Circuito"
        )
        database.definir_tipo_evento_tem_presidente(alvo["id"], True)
        assert self._tipos()["Assembleia de Circuito"] is True
        assert "Assembleia de Circuito" not in database.tipos_evento_sem_presidente()
        database.definir_tipo_evento_tem_presidente(alvo["id"], False)
        assert "Assembleia de Circuito" in database.tipos_evento_sem_presidente()

    def test_backup_antigo_nao_religa_a_assembleia(self):
        """Backup anterior à coluna cairia no DEFAULT 1 e estragaria o rodízio."""
        import json
        from pathlib import Path

        caminho, _ = exportar_backup()
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        for linha in dados["tabelas"]["tipos_evento_especial"]:
            linha.pop("tem_presidente", None)
        Path(caminho).write_text(
            json.dumps(dados, ensure_ascii=False), encoding="utf-8"
        )

        ok, _ = restaurar_backup(caminho)
        assert ok is True
        assert self._tipos()["Assembleia de Circuito"] is False
        assert self._tipos()["Discurso Especial"] is True

    def test_backup_novo_manda_no_que_o_usuario_escolheu(self):
        alvo = next(
            item for item in database.listar_tipos_evento()
            if item["nome"] == "Congresso Regional"
        )
        database.definir_tipo_evento_tem_presidente(alvo["id"], True)
        caminho, _ = exportar_backup()
        database.definir_tipo_evento_tem_presidente(alvo["id"], False)

        ok, _ = restaurar_backup(caminho)
        assert ok is True
        assert self._tipos()["Congresso Regional"] is True


class TestEscalaDePresidentes:
    """Restaurar backup antigo não pode esvaziar a escala das datas especiais."""

    def test_backup_antigo_remarca_os_anciaos(self):
        conn = get_connection()
        try:
            database.create_tables(conn)
            # datas_especiais aponta para o cadastro: sai antes, senão a FK
            # barra o DELETE (outros testes deixam datas gravadas).
            conn.execute("DELETE FROM datas_especiais")
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()
        database.salvar_presidente_cadastro("Um Ancião", "Ancião")
        database.salvar_presidente_cadastro("Um Servo", "Servo Ministerial")

        import json
        from pathlib import Path

        caminho, _ = exportar_backup()
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        for linha in dados["tabelas"]["presidentes_cadastro"]:
            linha.pop("preside_especiais", None)
        Path(caminho).write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

        ok, _ = restaurar_backup(caminho)
        assert ok is True
        por_nome = {p["nome"]: p for p in database.listar_presidentes_cadastro()}
        assert por_nome["Um Ancião"]["preside_especiais"] is True
        assert por_nome["Um Servo"]["preside_especiais"] is False

    def test_backup_novo_manda_no_que_o_usuario_escolheu(self):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM datas_especiais")
            conn.execute("DELETE FROM presidentes")
            conn.execute("DELETE FROM presidentes_cadastro")
            conn.commit()
        finally:
            conn.close()
        # Ancião deliberadamente fora das especiais: a restauração respeita.
        database.salvar_presidente_cadastro(
            "Fora das Especiais", "Ancião", preside_especiais=False)
        caminho, _ = exportar_backup()
        ok, _ = restaurar_backup(caminho)
        assert ok is True
        por_nome = {p["nome"]: p for p in database.listar_presidentes_cadastro()}
        assert por_nome["Fora das Especiais"]["preside_especiais"] is False


class TestOrigemDoBackup:
    """O arquivo diz de onde e de quando veio, para o aviso da restauração."""

    def test_exportado_traz_aparelho_e_data(self):
        _resetar_banco()
        caminho, _ = exportar_backup()
        resumo = database.resumo_backup(caminho)
        assert resumo["gerado_em"]
        assert resumo["aparelho"] in ("Celular",) or resumo["aparelho"].startswith(
            "Computador"
        )

    def test_backup_antigo_sem_aparelho_nao_quebra(self, tmp_path):
        arquivo = tmp_path / "antigo.json"
        arquivo.write_text(
            '{"app": "gestao-arranjo", "versao_backup": 1, '
            '"gerado_em": "2026-01-05T10:00:00", "tabelas": {}}',
            encoding="utf-8",
        )
        assert database.resumo_backup(arquivo) == {
            "gerado_em": "2026-01-05T10:00:00",
            "aparelho": "",
        }

    def test_arquivo_ilegivel_devolve_vazio(self, tmp_path):
        arquivo = tmp_path / "quebrado.json"
        arquivo.write_text("isto não é json", encoding="utf-8")
        assert database.resumo_backup(arquivo) == {"gerado_em": "", "aparelho": ""}
        assert database.resumo_backup(tmp_path / "nao_existe.json") == {
            "gerado_em": "",
            "aparelho": "",
        }

    def test_alteracao_local_acompanha_a_escrita_no_banco(self):
        _resetar_banco()
        antes = database.alterado_em_local()
        assert antes, "o banco existe, então a data de alteração não pode ser vazia"
        conn = get_connection()
        try:
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Depois')")
            conn.commit()
        finally:
            conn.close()
        assert database.alterado_em_local() >= antes


class TestVersaoDoEsquema:
    """O banco carrega o número do esquema em que está (PRAGMA user_version)."""

    def test_banco_marcado_apos_criar_tabelas(self):
        conn = get_connection()
        try:
            create_tables(conn)
            assert database.versao_esquema(conn) == database.ESQUEMA_ATUAL
        finally:
            conn.close()

    def test_migracao_numerada_roda_uma_vez_so(self, monkeypatch):
        """A segunda abertura do app não repete o que já foi aplicado."""
        chamadas = []

        def migracao_de_exemplo(conn):
            chamadas.append("rodou")
            conn.execute("CREATE TABLE IF NOT EXISTS exemplo_migracao (id INTEGER)")

        monkeypatch.setattr(database, "MIGRACOES", [(2, migracao_de_exemplo)])
        monkeypatch.setattr(database, "ESQUEMA_ATUAL", 2)

        conn = get_connection()
        try:
            database._marcar_esquema(conn, 1)
            create_tables(conn)
            assert chamadas == ["rodou"]
            assert database.versao_esquema(conn) == 2

            create_tables(conn)
            assert chamadas == ["rodou"], "migração aplicada de novo"
        finally:
            conn.execute("DROP TABLE IF EXISTS exemplo_migracao")
            conn.commit()
            conn.close()

    def test_banco_antigo_passa_pela_migracao_pendente(self, monkeypatch):
        """Quem está numa versão anterior recebe só o que falta."""
        aplicadas = []
        monkeypatch.setattr(
            database,
            "MIGRACOES",
            [
                (2, lambda conn: aplicadas.append(2)),
                (3, lambda conn: aplicadas.append(3)),
            ],
        )
        monkeypatch.setattr(database, "ESQUEMA_ATUAL", 3)

        conn = get_connection()
        try:
            database._marcar_esquema(conn, 2)
            create_tables(conn)
            assert aplicadas == [3]
            assert database.versao_esquema(conn) == 3
        finally:
            conn.close()
