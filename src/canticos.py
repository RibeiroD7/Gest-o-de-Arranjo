"""Catálogo dos cânticos de *Cante de Coração para Jeová* (sjjls-T).

Número, título e texto bíblico dos 151 cânticos. Serve para montar a mensagem
da presidência: o coordenador digita só o número e o app completa o resto.

Extraído do PDF oficial ``sjjls_T.pdf`` (edição de março de 2020, pt-BR).
"""

from __future__ import annotations

# {número: (título, texto bíblico)}
CANTICOS: dict[int, tuple[str, str]] = {
    1: ('As qualidades de Jeová', 'Apocalipse 4:11'),
    2: ('Teu nome é Jeová', 'Salmo 83:18'),
    3: ('Jeová, minha força e esperança', 'Provérbios 14:26'),
    4: ('“Jeová é o meu Pastor”', 'Salmo 23'),
    5: ('As obras maravilhosas de Deus', 'Salmo 139'),
    6: ('Os céus declaram a glória de Deus', 'Salmo 19'),
    7: ('Jeová, nossa força e poder', 'Isaías 12:2'),
    8: ('Jeová é um refúgio', 'Salmo 91'),
    9: ('Jeová é nosso Rei!', 'Salmo 97:1'),
    10: ('A Jeová vou agradecer!', 'Salmo 145:12'),
    11: ('A criação dá glória a Jeová', 'Salmo 19'),
    12: ('Nosso grandioso Deus, Jeová', 'Êxodo 34:6, 7'),
    13: ('Cristo, o nosso exemplo', '1 Pedro 2:21'),
    14: ('O novo Rei da Terra', 'Salmo 2:12'),
    15: ('Louve o Filho de Jeová!', 'Hebreus 1:6'),
    16: ('Jeová escolheu nosso Rei', 'Apocalipse 21:2'),
    17: ('“Eu quero!”', 'Lucas 5:13'),
    18: ('Obrigado pelo resgate!', 'Lucas 22:20'),
    19: ('A Ceia do Senhor', 'Mateus 26:26-30'),
    20: ('Jeová nos deu o seu melhor', '1 João 4:9'),
    21: ('Vou buscar primeiro o Reino', 'Mateus 6:33'),
    22: ('Que venha o Reino de Deus!', 'Apocalipse 11:15; 12:10'),
    23: ('Jeová começou a reinar!', 'Apocalipse 11:15'),
    24: ('Venham para o monte de Jeová!', 'Isaías 2:2-4'),
    25: ('Os filhos ungidos de Jeová', '1 Pedro 2:9'),
    26: ('“Se fez por meus irmãos, você fez por mim”', 'Mateus 25:34-40'),
    27: ('A vitória dos filhos de Deus', 'Romanos 8:19'),
    28: ('Quem pode ser amigo de Jeová?', 'Salmo 15'),
    29: ('Que nossa vida dê honra ao teu nome!', 'Isaías 43:10-12'),
    30: ('Meu Deus, meu Amigo e Pai', 'Hebreus 6:10'),
    31: ('Ande com Deus', 'Miqueias 6:8'),
    32: ('Escolha o lado de Jeová!', 'Êxodo 32:26'),
    33: ('Deixe Jeová levar seus fardos', 'Salmo 55'),
    34: ('Andarei em integridade', 'Salmo 26'),
    35: ('O que é mais importante', 'Filipenses 1:10'),
    36: ('Proteja o coração', 'Provérbios 4:23'),
    37: ('Amo a Jeová de todo o coração', 'Mateus 22:37'),
    38: ('Jeová vai te dar força', '1 Pedro 5:10'),
    39: ('Um bom nome', 'Eclesiastes 7:1'),
    40: ('Você já decidiu?', 'Romanos 14:8'),
    41: ('Escuta minha oração', 'Salmo 54'),
    42: ('Minha oração a Jeová', 'Efésios 6:18'),
    43: ('Uma oração de agradecimento', 'Salmo 95:2'),
    44: ('Oração de um servo aflito', 'Salmo 4:1'),
    45: ('Os pensamentos do meu coração', 'Salmo 19:14'),
    46: ('Obrigado, Jeová!', '1 Tessalonicenses 5:18'),
    47: ('Sempre a Deus vou orar', '1 Tessalonicenses 5:17'),
    48: ('Caminhamos sempre com Jeová', 'Miqueias 6:8'),
    49: ('Como alegrar a Jeová', 'Provérbios 27:11'),
    50: ('Minha oração de dedicação', 'Mateus 22:37'),
    51: ('Dedicamos nossa vida a Jeová', 'Mateus 16:24'),
    52: ('Nossa dedicação', 'Hebreus 10:7, 9'),
    53: ('Pronto para pregar', 'Jeremias 1:17'),
    54: ('“Este é o caminho”', 'Isaías 30:20, 21'),
    55: ('Nada temam, meus amados!', 'Mateus 10:28'),
    56: ('Faça da verdade a sua vida', 'Provérbios 3:1, 2'),
    57: ('Pregue a todo tipo de pessoas', '1 Timóteo 2:4'),
    58: ('Procuramos os amigos da paz', 'Lucas 10:6'),
    59: ('Vamos louvar a Jeová!', 'Salmo 146:2'),
    60: ('A mensagem de vida', 'Ezequiel 3:17-19'),
    61: ('Avancem, Testemunhas!', 'Lucas 16:16'),
    62: ('O novo cântico', 'Salmo 98'),
    63: ('Somos Testemunhas de Jeová!', 'Isaías 43:10-12'),
    64: ('Participamos com alegria na colheita', 'Mateus 13:1-23'),
    65: ('Confiantes, nós vamos continuar!', 'Hebreus 6:1'),
    66: ('Vamos declarar as boas novas', 'Apocalipse 14:6, 7'),
    67: ('“Pregue a palavra”', '2 Timóteo 4:2'),
    68: ('Plantando a semente do Reino', 'Mateus 13:4-8'),
    69: ('Continue pregando!', '2 Timóteo 4:5'),
    70: ('Procurem os merecedores', 'Mateus 10:11-15'),
    71: ('Marchamos com Jeová', 'Efésios 6:11-14'),
    72: ('Pregar as verdades do Reino', 'Atos 20:20, 21'),
    73: ('Dá-nos coragem', 'Atos 4:29'),
    74: ('A canção do Reino', 'Salmo 98:1'),
    75: ('‘Estou aqui!’', 'Isaías 6:8'),
    76: ('Um sentimento especial', 'Hebreus 13:15'),
    77: ('Luz num mundo sombrio', '2 Coríntios 4:6'),
    78: ('Ensine a verdade com amor', 'Atos 18:11'),
    79: ('Ensine-os a se manter firmes', 'Mateus 28:19, 20'),
    80: ('“Provem e vejam que Jeová é bom”', 'Salmo 34:8'),
    81: ('A vida de um pioneiro', 'Eclesiastes 11:6'),
    82: ('‘Deixe a luz brilhar’', 'Mateus 5:16'),
    83: ('“De casa em casa”', 'Atos 20:20'),
    84: ('Vamos fazer nosso melhor', 'Mateus 9:37, 38'),
    85: ('Sejam bem-vindos!', 'Romanos 15:7'),
    86: ('As reuniões são o nosso lugar', 'Isaías 50:4; 54:13'),
    87: ('As reuniões nos encorajam', 'Hebreus 10:24, 25'),
    88: ('Os teus caminhos quero entender', 'Salmo 25:4'),
    89: ('Escute, obedeça e seja abençoado', 'Lucas 11:28'),
    90: ('“Encorajando uns aos outros”', 'Hebreus 10:24, 25'),
    91: ('Construímos com amor', 'Salmo 127:1'),
    92: ('Um lugar que leva teu nome', '1 Crônicas 29:16'),
    93: ('Abençoa nossas reuniões', 'Hebreus 10:24, 25'),
    94: ('Muito obrigado pela Bíblia', 'Filipenses 2:16'),
    95: ('A luz clareia mais e mais', 'Provérbios 4:18'),
    96: ('O livro de Deus é um tesouro', 'Provérbios 2:1, 4'),
    97: ('A Palavra de Deus nos ajuda a viver', 'Mateus 4:4'),
    98: ('A Bíblia, um presente de Deus', '2 Timóteo 3:16, 17'),
    99: ('Muitos irmãos ao meu lado', 'Apocalipse 7:9, 10'),
    100: ('Vamos ser hospitaleiros!', 'Atos 17:7'),
    101: ('Servimos a Jeová em união', 'Efésios 4:3'),
    102: ('Ajude os que estão fracos', 'Atos 20:35'),
    103: ('Os anciãos são um presente de Jeová', 'Efésios 4:8'),
    104: ('Espírito santo — um presente de Deus', 'Lucas 11:13'),
    105: ('“Deus é amor”', '1 João 4:7, 8'),
    106: ('Amor — a qualidade que é sem igual', '1 Coríntios 13:1-8'),
    107: ('Jeová — o exemplo perfeito de amor', '1 João 4:19'),
    108: ('O amor leal de Jeová', 'Isaías 55:1-3'),
    109: ('Mostre amor de coração', '1 Pedro 1:22'),
    110: ('“A alegria que vem de Jeová”', 'Neemias 8:10'),
    111: ('Nossos motivos de alegria', 'Mateus 5:12'),
    112: ('Jeová, Deus de paz', 'Filipenses 4:9'),
    113: ('A paz que vem de Deus', 'João 14:27'),
    114: ('Seja paciente', 'Tiago 5:8'),
    115: ('A paciência de Deus é salvação', '2 Pedro 3:15'),
    116: ('A força da bondade', 'Efésios 4:32'),
    117: ('A qualidade da bondade', '2 Crônicas 6:41'),
    118: ('Jeová, a ti pedimos mais fé', 'Lucas 17:5'),
    119: ('Temos que ter fé', 'Hebreus 10:38, 39'),
    120: ('Seja humilde como Jesus', 'Mateus 11:28-30'),
    121: ('Precisamos ter autodomínio', 'Romanos 7:14-25'),
    122: ('Vamos continuar firmes!', '1 Coríntios 15:58'),
    123: ('Obedecemos a Jeová e à sua organização', '1 Coríntios 14:33'),
    124: ('Sempre leais', 'Salmo 18:25'),
    125: ('“Felizes os misericordiosos”', 'Mateus 5:7'),
    126: ('Sempre fortes, firmes e despertos', '1 Coríntios 16:13'),
    127: ('Que tipo de pessoa eu devo ser', '2 Pedro 3:11'),
    128: ('Persevere até o fim', 'Mateus 24:13'),
    129: ('Eu vou perseverar', 'Mateus 24:13'),
    130: ('Vamos perdoar uns aos outros', 'Salmo 86:5'),
    131: ('O que Jeová uniu', 'Mateus 19:5, 6'),
    132: ('Nós somos um', 'Gênesis 2:23, 24'),
    133: ('Quero ser um jovem leal', 'Eclesiastes 12:1'),
    134: ('Os filhos são uma herança de Deus', 'Salmo 127:3-5'),
    135: ('“Seja sábio, meu filho”', 'Provérbios 27:11'),
    136: ('Jeová o recompensará', 'Rute 2:12'),
    137: ('Mulheres fiéis', 'Romanos 16:2'),
    138: ('A beleza dos cabelos brancos', 'Provérbios 16:31'),
    139: ('Imagine a si mesmo no Paraíso', 'Apocalipse 21:1-5'),
    140: ('Vida eterna, enfim!', 'João 3:16'),
    141: ('O milagre da vida', 'Salmo 36:9'),
    142: ('A esperança que nos dá coragem', 'Hebreus 6:18, 19'),
    143: ('Continue ativo e desperto!', 'Romanos 8:20-25'),
    144: ('Olhe para as bênçãos!', '2 Coríntios 4:18'),
    145: ('Deus prometeu um paraíso', 'Lucas 23:43'),
    146: ('“Estou fazendo novas todas as coisas”', 'Apocalipse 21:1-5'),
    147: ('A vida eterna — que bela promessa!', 'Salmo 37:29'),
    148: ('Jeová é nosso Salvador', '2 Samuel 22:1-8'),
    149: ('Um cântico de vitória', 'Êxodo 15:1'),
    150: ('Busquem a Deus para obter livramento', 'Sofonias 2:3'),
    151: ('Ele chamará', 'Jó 14:13-15'),
}

TOTAL_CANTICOS = len(CANTICOS)


def titulo_cantico(numero: int | str | None) -> str:
    """Título do cântico, sem o número (vazio se o número não existir)."""
    try:
        return CANTICOS[int(numero)][0]
    except (TypeError, ValueError, KeyError):
        return ""


def texto_biblico_cantico(numero: int | str | None) -> str:
    """Texto bíblico que acompanha o cântico (vazio se não existir)."""
    try:
        return CANTICOS[int(numero)][1]
    except (TypeError, ValueError, KeyError):
        return ""


def rotulo_cantico(numero: int | str | None) -> str:
    """Cântico como vai na mensagem: ``34 - Andarei em integridade (Salmo 26)``.

    Devolve string vazia quando o número não corresponde a nenhum cântico —
    quem chama decide o que fazer (avisar ou omitir a linha).
    """
    try:
        nr = int(numero)
    except (TypeError, ValueError):
        return ""
    dados = CANTICOS.get(nr)
    if not dados:
        return ""
    titulo, texto = dados
    return f"{nr} - {titulo} ({texto})" if texto else f"{nr} - {titulo}"
