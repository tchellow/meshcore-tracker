#!/usr/bin/env bash
# Cria o pacote .deb. Roda no Python e no WebKit do sistema, com as demais bibliotecas no pacote.
# Uso: bash instalador/criar_deb.sh 0.1.0
# Use o Python mais antigo suportado (3.10), para o pacote servir nos Ubuntus mais novos.
set -euo pipefail

VERSAO="$1"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SAIDA="$RAIZ/instalador-saida"
PACOTE="$(mktemp -d)/meshcore-tracker"
APP="$PACOTE/opt/meshcore-tracker"

mkdir -p "$PACOTE/DEBIAN" \
         "$APP/assets" \
         "$PACOTE/usr/bin" \
         "$PACOTE/usr/share/applications" \
         "$PACOTE/usr/share/icons/hicolor/256x256/apps" \
         "$PACOTE/usr/share/icons/hicolor/scalable/apps" \
         "$PACOTE/usr/lib/udev/rules.d" \
         "$PACOTE/usr/share/doc/meshcore-tracker" \
         "$SAIDA"

cp "$RAIZ"/{app,automacao,banco,janela,portas,radio,versao}.py "$APP/"
cp -r "$RAIZ/static" "$APP/static"
cp "$RAIZ/assets/icone-256.png" "$APP/assets/"

python3 -m pip install --quiet --disable-pip-version-check --target "$APP/lib" -r "$RAIZ/requirements.txt"
# O programa so usa USB. A biblioteca meshcore trata o Bluetooth como opcional.
rm -rf "$APP/lib/bleak" "$APP/lib/bleak-"* "$APP/lib/dbus_fast" "$APP/lib/dbus_fast-"* "$APP/lib/bin"
find "$APP/lib" -type d -name __pycache__ -prune -exec rm -rf {} +

cat > "$PACOTE/usr/bin/meshcore-tracker" <<'FIM'
#!/bin/sh
export PYTHONPATH=/opt/meshcore-tracker/lib
export PYTHONDONTWRITEBYTECODE=1
exec /usr/bin/python3 /opt/meshcore-tracker/app.py --registro-em-arquivo "$@"
FIM
chmod 755 "$PACOTE/usr/bin/meshcore-tracker"

cp "$RAIZ/assets/icone-256.png" "$PACOTE/usr/share/icons/hicolor/256x256/apps/meshcore-tracker.png"
cp "$RAIZ/static/icone.svg" "$PACOTE/usr/share/icons/hicolor/scalable/apps/meshcore-tracker.svg"
cp "$RAIZ/LICENSE" "$PACOTE/usr/share/doc/meshcore-tracker/copyright"

cat > "$PACOTE/usr/share/applications/meshcore-tracker.desktop" <<'FIM'
[Desktop Entry]
Type=Application
Name=Meshcore Tracker
Comment=Telemetria periodica e mapa de contatos MeshCore
Exec=meshcore-tracker
Icon=meshcore-tracker
Terminal=false
Categories=Network;HamRadio;
StartupWMClass=meshcore-tracker
FIM

# Da ao usuario da sessao acesso a portas seriais USB, sem precisar do grupo dialout.
cat > "$PACOTE/usr/lib/udev/rules.d/70-meshcore-tracker.rules" <<'FIM'
SUBSYSTEM=="tty", SUBSYSTEMS=="usb", TAG+="uaccess"
FIM

TAMANHO="$(du -sk "$PACOTE" | cut -f1)"
cat > "$PACOTE/DEBIAN/control" <<FIM
Package: meshcore-tracker
Version: $VERSAO
Section: hamradio
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, xdg-utils
Installed-Size: $TAMANHO
Maintainer: tchellow <tchellow@users.noreply.github.com>
Homepage: https://github.com/tchellow/meshcore-tracker
Description: Telemetria periodica e mapa de contatos MeshCore
 Conecta em um radio MeshCore companion pela USB, pede telemetria com
 posicao de um ou mais contatos periodicamente e mostra no mapa.
FIM

cat > "$PACOTE/DEBIAN/postinst" <<'FIM'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=tty --action=change || true
fi
FIM
chmod 755 "$PACOTE/DEBIAN/postinst"

cat > "$PACOTE/DEBIAN/prerm" <<'FIM'
#!/bin/sh
pkill -f /opt/meshcore-tracker/app.py || true
exit 0
FIM
chmod 755 "$PACOTE/DEBIAN/prerm"

chmod -R u=rwX,go=rX "$PACOTE/opt" "$PACOTE/usr"
dpkg-deb --root-owner-group --build "$PACOTE" "$SAIDA/MeshcoreTracker-$VERSAO-ubuntu-amd64.deb"
