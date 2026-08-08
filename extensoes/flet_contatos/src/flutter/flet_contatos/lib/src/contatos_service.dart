import 'package:flet/flet.dart';
import 'package:flutter_contacts/flutter_contacts.dart';

/// Abre o seletor de contatos do sistema e devolve o contato escolhido.
///
/// O seletor em si não pede permissão, mas trazer o TELEFONE do escolhido
/// pede — por isso pedimos antes. Se o usuário negar, devolvemos null e o app
/// cai no caminho do arquivo .vcf.
class ContatosService extends FletService {
  ContatosService({required super.control});

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_invokeMethod);
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    switch (name) {
      case "escolher":
        return await _escolher();
      default:
        throw Exception("Método desconhecido em Contatos: $name");
    }
  }

  Future<Map<String, dynamic>?> _escolher() async {
    if (!await FlutterContacts.permissions.has(PermissionType.read)) {
      final status = await FlutterContacts.permissions.request(
        PermissionType.read,
      );
      if (status != PermissionStatus.granted &&
          status != PermissionStatus.limited) {
        return null;
      }
    }

    final contato = await FlutterContacts.native.showPicker(
      properties: {ContactProperty.phone},
    );
    if (contato == null) {
      return null; // usuário cancelou
    }
    return {
      "nome": contato.displayName,
      "telefones": contato.phones.map((p) => p.number).toList(),
    };
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(_invokeMethod);
    super.dispose();
  }
}
