"""Leitura dos dados de uma congregação a partir de texto colado.

O texto colado nunca vem do mesmo jeito: às vezes com rótulos, às vezes com
as duas reuniões em colunas que viram uma linha só, às vezes só o pedaço que
a pessoa selecionou. O que interessa é sempre a reunião do FIM DE SEMANA.
"""

from texto_congregacao import ler_congregacao_colada

# Uma ficha completa, com as duas reuniões e o endereço em várias linhas.
FICHA = """CONGREGAÇÃO
Vila Palmira - São Paulo SP
10 km (6 mi)
Reunião do meio de semana
Quarta-feira, 19:45
Reunião do fim de semana
Sábado, 19:30
Endereço
R. Satulnino de Oliveira, 44
Jardim São Luis
São Paulo, SP
05813-080
Telefone
Coordenadas GPS: -23.655528 -46.731913"""


class TestFichaCompleta:
    def test_separa_todos_os_campos(self):
        dados = ler_congregacao_colada(FICHA)
        assert dados["nome"] == "Vila Palmira"
        assert dados["dia_semana"] == "Sábado"
        assert dados["horario"] == "19:30"
        assert dados["endereco"].startswith("R. Satulnino de Oliveira, 44")
        assert "Jardim São Luis" in dados["endereco"]

    def test_pega_o_fim_de_semana_e_nao_o_meio(self):
        """19:45 na quarta é a reunião do meio de semana; não é o discurso."""
        dados = ler_congregacao_colada(FICHA)
        assert dados["horario"] != "19:45"
        assert dados["dia_semana"] == "Sábado"

    def test_o_cep_fecha_o_endereco(self):
        dados = ler_congregacao_colada(FICHA)
        assert "05813-080" in dados["endereco"]
        assert "Coordenadas" not in dados["endereco"]

    def test_telefone_ausente_volta_vazio(self):
        """A ficha traz o rótulo Telefone sem número embaixo."""
        assert ler_congregacao_colada(FICHA)["telefone"] == ""


class TestOutrosFormatos:
    def test_duas_colunas_viradas_numa_linha_so(self):
        """Copiar a tabela de duas colunas junta as duas reuniões na mesma linha."""
        texto = (
            "Jardim das Palmas - São Paulo SP\n"
            "Reunião do meio de semana Reunião do fim de semana\n"
            "Quinta-feira, 19:30 Domingo, 09:00\n"
        )
        dados = ler_congregacao_colada(texto)
        assert dados["nome"] == "Jardim das Palmas"
        assert (dados["dia_semana"], dados["horario"]) == ("Domingo", "09:00")

    def test_texto_solto_de_mensagem(self):
        """O jeito que chega no WhatsApp, sem rótulo nenhum."""
        texto = "Parque Regina, domingo 17h00, R. Leopoldino José de Camargo, 210"
        dados = ler_congregacao_colada(texto)
        assert dados["dia_semana"] == "Domingo"
        assert dados["horario"] == "17:00"

    def test_telefone_quando_existe(self):
        texto = "Palmira\nSábado, 19:30\nTelefone\n(11) 99162-1641"
        assert ler_congregacao_colada(texto)["telefone"] == "(11) 99162-1641"

    def test_horario_com_um_digito_na_hora(self):
        texto = "Morumbi\nDomingo, 9:15"
        assert ler_congregacao_colada(texto)["horario"] == "09:15"

    def test_nome_sem_sufixo_de_cidade_fica_inteiro(self):
        assert ler_congregacao_colada("Palmira\nSábado, 19:30")["nome"] == "Palmira"


class TestTextoQueNaoServe:
    def test_texto_vazio(self):
        assert ler_congregacao_colada("") == {
            "nome": "", "dia_semana": "", "horario": "", "endereco": "", "telefone": "",
        }

    def test_sem_dia_nem_horario_devolve_o_resto_vazio(self):
        dados = ler_congregacao_colada("Um texto qualquer que não é uma ficha")
        assert dados["dia_semana"] == ""
        assert dados["horario"] == ""

    def test_so_o_dia_sem_horario_nao_inventa_hora(self):
        dados = ler_congregacao_colada("Congregação\nJardim Paris\nSábado")
        assert dados["nome"] == "Jardim Paris"
        assert dados["horario"] == ""
