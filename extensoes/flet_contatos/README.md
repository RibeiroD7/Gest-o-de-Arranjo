# flet-contatos

Extensão do Flet que abre o **seletor de contatos do próprio aparelho**
(Android/iOS) e devolve o contato escolhido para o app.

O Flet não expõe a agenda do celular: os serviços que ele traz são Share,
FilePicker, Clipboard e sensores. Para chegar nos contatos é preciso empacotar
um pacote Flutter — é o que esta extensão faz, sobre o
[`flutter_contacts`](https://pub.dev/packages/flutter_contacts).

## Como o app usa

```python
from flet_contatos import Contatos

contatos = Contatos()          # criado junto dos demais serviços, no main()
escolhido = await contatos.escolher()
# {"nome": "Fábio Moreira", "telefones": ["11999998888"]} ou None se cancelou
```

## Plataformas

| Plataforma | Situação |
| --- | --- |
| Android | Seletor nativo (pede a permissão de contatos na primeira vez) |
| iOS / macOS | Suportado pelo `flutter_contacts` (o app não é publicado neles hoje) |
| Windows / Linux | **Sem suporte** — a extensão nem entra nesses builds |

No computador o app não mostra o botão do seletor nativo; quem quiser importar
telefones usa o arquivo `.vcf` (ver `src/contatos.py` no app).

## Estrutura

```
src/flet_contatos/            lado Python (o serviço que o app chama)
src/flutter/flet_contatos/    lado Dart (fala com o pacote flutter_contacts)
```

O `flet build apk` monta os dois lados: o app declara esta pasta em
`[tool.flet.dev_packages]` no `pyproject.toml` da raiz.
