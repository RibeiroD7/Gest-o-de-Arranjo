"""Catálogo de cânticos e a mensagem da presidência.

O catálogo foi extraído do PDF oficial (sjjsm-T) uma única vez e virou código;
estes testes travam o resultado dessa extração — especialmente os acentos, que
o extrator do PDF entrega separados da letra ("Jeov ´a") e precisaram ser
remontados.
"""

import pytest

from canticos import (
    CANTICOS,
    TOTAL_CANTICOS,
    rotulo_cantico,
    texto_biblico_cantico,
    titulo_cantico,
)
from servicos import montar_mensagem_presidencia


class TestCatalogo:
    def test_tem_os_159_canticos_sem_buracos(self):
        assert TOTAL_CANTICOS == 159
        assert sorted(CANTICOS) == list(range(1, 160))

    def test_todos_tem_titulo_e_texto_biblico(self):
        assert all(titulo and texto for titulo, texto in CANTICOS.values())

    def test_acentos_foram_remontados(self):
        # Sobras da extração: diacrítico solto ou grudado na palavra seguinte.
        soltos = [c for c in "´˜ˆ¸`" if any(c in t for t, _ in CANTICOS.values())]
        assert not soltos
        assert CANTICOS[8][0] == "Jeová é um refúgio"
        assert CANTICOS[123][0] == "Obedecemos a Jeová e à sua organização"

    def test_numeros_conhecidos(self):
        assert CANTICOS[34] == ("Andarei em integridade", "Salmo 26")
        assert CANTICOS[151] == ("Ele chamará", "Jó 14:13-15")
        assert CANTICOS[159] == ("Toda a glória vou te dar", "Salmo 96:8")


class TestRotulo:
    def test_formato_da_mensagem(self):
        assert rotulo_cantico(34) == "34 - Andarei em integridade (Salmo 26)"

    def test_aceita_texto_do_campo(self):
        assert rotulo_cantico("34") == rotulo_cantico(34)

    @pytest.mark.parametrize("invalido", [None, "", "abc", 0, 160, "12,5"])
    def test_numero_invalido_vira_vazio(self, invalido):
        assert rotulo_cantico(invalido) == ""
        assert titulo_cantico(invalido) == ""
        assert texto_biblico_cantico(invalido) == ""


class TestMensagemPresidencia:
    def test_formato_combinado_com_o_usuario(self):
        assert montar_mensagem_presidencia(
            rotulo_cantico(34),
            "Carlos Menezes",
            "Jardim Maria Sampaio",
            "Ande no caminho da integridade",
        ) == (
            "Cântico: 34 - Andarei em integridade (Salmo 26)\n"
            "Orador: Carlos Menezes\n"
            "Congregação: Jardim Maria Sampaio\n"
            "Tema: Ande no caminho da integridade"
        )

    def test_campos_vazios_ficam_visiveis_como_pendencia(self):
        mensagem = montar_mensagem_presidencia("", "  ", None, "Tema")
        assert mensagem.splitlines() == [
            "Cântico: —",
            "Orador: —",
            "Congregação: —",
            "Tema: Tema",
        ]
