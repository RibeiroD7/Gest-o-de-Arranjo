import 'dart:convert';

import 'package:flet/flet.dart';
import 'package:flutter_contacts/flutter_contacts.dart';

/// Ponte com a agenda do aparelho: escolher um contato e reler os escolhidos.
///
/// O seletor em si não pede permissão, mas trazer TELEFONE e FOTO do escolhido
/// pede — por isso pedimos antes. Negada, devolvemos null e o app cai no
/// caminho do arquivo .vcf.
class ContatosService extends FletService {
  ContatosService({required super.control});

  // photoThumbnail basta para o avatar e é bem mais leve que a foto cheia.
  static const _propriedades = <ContactProperty>{
    ContactProperty.phone,
    ContactProperty.photoThumbnail,
    ContactProperty.identifiers,
  };

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_invokeMethod);
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    switch (name) {
      case "escolher":
        return await _escolher();
      case "reler":
        return await _reler(
          (args["ids"] as List).map((e) => e.toString()).toList(),
        );
      default:
        throw Exception("Método desconhecido em Contatos: $name");
    }
  }

  Future<bool> _temPermissao() async {
    if (await FlutterContacts.permissions.has(PermissionType.read)) {
      return true;
    }
    final status = await FlutterContacts.permissions.request(
      PermissionType.read,
    );
    return status == PermissionStatus.granted ||
        status == PermissionStatus.limited;
  }

  /// Chave estável do contato: sobrevive a sincronizações e junções de
  /// contatos no Android, ao contrário do id, que pode mudar.
  /// Sem chave nenhuma devolvemos "", e o app trata como "sem vínculo" — o
  /// telefone é salvo do mesmo jeito, só não acompanha mudanças na agenda.
  String _chave(Contact contato) =>
      contato.android?.identifiers?.lookupKey ?? contato.id ?? "";

  Map<String, dynamic> _paraMapa(Contact contato, {String? chave}) {
    final foto = contato.photo?.thumbnail ?? contato.photo?.fullSize;
    return {
      "id": chave ?? _chave(contato),
      "nome": contato.displayName,
      "telefones": contato.phones.map((p) => p.number).toList(),
      "foto": foto == null ? null : base64Encode(foto),
    };
  }

  Future<Map<String, dynamic>?> _escolher() async {
    if (!await _temPermissao()) return null;

    final escolhido = await FlutterContacts.native.showPicker(
      properties: _propriedades,
    );
    if (escolhido == null) return null; // usuário cancelou
    return _paraMapa(escolhido);
  }

  /// Relê os contatos já vinculados, para o app acompanhar o que mudou na
  /// agenda. Um contato apagado no aparelho volta como ausente da lista.
  Future<List<Map<String, dynamic>>> _reler(List<String> ids) async {
    if (ids.isEmpty || !await _temPermissao()) return [];

    final atualizados = <Map<String, dynamic>>[];
    for (final id in ids) {
      try {
        final contato = await FlutterContacts.get(
          id,
          properties: _propriedades,
          androidLookup: true,
        );
        if (contato != null) {
          atualizados.add(_paraMapa(contato, chave: id));
        }
      } catch (_) {
        // Contato sumiu ou a chave não vale mais: mantém o que o app já tem.
      }
    }
    return atualizados;
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(_invokeMethod);
    super.dispose();
  }
}
