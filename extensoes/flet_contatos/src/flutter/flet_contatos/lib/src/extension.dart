import 'package:flet/flet.dart';

import 'contatos_service.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "Contatos":
        return ContatosService(control: control);
      default:
        return null;
    }
  }
}
