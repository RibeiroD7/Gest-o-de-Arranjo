"""Exportação do mês para a agenda (.ics).

O arquivo é lido por Google Agenda, Outlook e iPhone: o que estiver fora do
padrão não dá erro, simplesmente não aparece na agenda de quem importou.
"""

from datetime import date, datetime

from agenda_ics import _dobrar, _escapar, eventos_do_mes, gerar_ics

RECEBIDOS = {
    "05/09/2026": {
        "orador": "Orador Um",
        "tema_nr": 12,
        "tema": "O que a Bíblia diz sobre o futuro",
        "congregacao": "Vila Nova",
    },
    "10/10/2026": {"orador": "De outro mês", "tema_nr": 3, "tema": "", "congregacao": ""},
}
ENVIADOS = {
    "19/09/2026": [
        {"orador": "Orador Dois", "tema_nr": 7, "tema": "Tema Sete",
         "congregacao": "Jardim Alfa", "status": "pendente"},
        {"orador": "Orador Três", "tema_nr": 9, "tema": "Tema Nove",
         "congregacao": "Centro", "status": "confirmado"},
    ]
}
PRESIDENTES = {"05/09/2026": {"nome": "Presidente Um"}}
ESPECIAIS = {
    "26/09/2026": {"tipo": "Assembleia de Circuito", "orador": "", "tema": "",
                   "presidente_nome": ""}
}


class TestEventosDoMes:
    def test_pega_so_o_mes_pedido(self):
        eventos = eventos_do_mes(2026, 9, RECEBIDOS, ENVIADOS, PRESIDENTES, ESPECIAIS)
        assert [e["data"] for e in eventos] == [
            date(2026, 9, 5), date(2026, 9, 19), date(2026, 9, 19), date(2026, 9, 26)
        ]

    def test_recebido_traz_orador_congregacao_tema_e_presidente(self):
        evento = eventos_do_mes(2026, 9, RECEBIDOS, {}, PRESIDENTES)[0]
        assert evento["titulo"] == "Discurso: Orador Um (Vila Nova)"
        assert "Tema 12: O que a Bíblia diz sobre o futuro" in evento["descricao"]
        assert "Presidente: Presidente Um" in evento["descricao"]

    def test_enviado_diz_para_onde_vai_e_marca_o_que_falta_confirmar(self):
        eventos = eventos_do_mes(2026, 9, {}, ENVIADOS)
        titulos = [e["titulo"] for e in eventos]
        assert "Orador Dois discursa em Jardim Alfa" in titulos
        pendente = next(e for e in eventos if "Orador Dois" in e["titulo"])
        confirmado = next(e for e in eventos if "Orador Três" in e["titulo"])
        assert "Ainda sem confirmação." in pendente["descricao"]
        assert "Ainda sem confirmação." not in confirmado["descricao"]

    def test_dois_envios_no_mesmo_dia_nao_disputam_o_mesmo_uid(self):
        eventos = eventos_do_mes(2026, 9, {}, ENVIADOS)
        assert len({e["uid"] for e in eventos}) == 2

    def test_data_estragada_no_banco_nao_derruba_a_exportacao(self):
        assert eventos_do_mes(2026, 9, {"sem data": {"orador": "X"}}, {}) == []


class TestGerarIcs:
    def test_estrutura_minima_do_arquivo(self):
        texto = gerar_ics(
            [{"data": date(2026, 9, 5), "titulo": "Discurso", "descricao": "",
              "uid": "recebido-20260905"}],
            agora=datetime(2026, 8, 24, 12, 0),
        )
        assert texto.startswith("BEGIN:VCALENDAR\r\n")
        assert texto.endswith("END:VCALENDAR\r\n")
        assert "UID:recebido-20260905@gestao-arranjo" in texto
        assert "DTSTART;VALUE=DATE:20260905" in texto
        # Dia inteiro: o fim é o dia seguinte, como manda o padrão.
        assert "DTEND;VALUE=DATE:20260906" in texto

    def test_sem_descricao_nao_escreve_o_campo(self):
        texto = gerar_ics([{"data": date(2026, 9, 5), "titulo": "X", "uid": "u"}])
        assert "DESCRIPTION" not in texto

    def test_toda_linha_cabe_no_limite_do_padrao(self):
        titulo = "Discurso: " + "Nome Bem Comprido " * 8
        texto = gerar_ics([{"data": date(2026, 9, 5), "titulo": titulo,
                            "descricao": titulo, "uid": "u"}])
        for linha in texto.split("\r\n"):
            assert len(linha.encode("utf-8")) <= 75, linha

    def test_continuacao_comeca_com_espaco(self):
        texto = gerar_ics([{"data": date(2026, 9, 5), "titulo": "A" * 200, "uid": "u"}])
        linhas = texto.split("\r\n")
        resumo = next(linha for linha in linhas if linha.startswith("SUMMARY"))
        seguinte = linhas[linhas.index(resumo) + 1]
        assert seguinte.startswith(" ")


class TestEscapar:
    def test_reservados_do_formato(self):
        assert _escapar("a,b") == "a" + chr(92) + ",b"
        assert _escapar("a;b") == "a" + chr(92) + ";b"
        assert _escapar("linha 1" + chr(10) + "linha 2") == "linha 1" + chr(92) + "nlinha 2"

    def test_barra_vira_barra_dupla(self):
        assert _escapar(chr(92)) == chr(92) * 2

    def test_texto_curto_nao_e_dobrado(self):
        assert _dobrar("SUMMARY:curto") == ["SUMMARY:curto"]
