#!/usr/bin/env bash
# Cria o pacote .deb a partir de dist/meshcore-tracker.
# Uso: bash instalador/criar_deb.sh 0.1.0
set -euo pipefail

VERSAO="$1"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SAIDA="$RAIZ/instalador-saida"
PACOTE="$(mktemp -d)/meshcore-tracker"

mkdir -p "$PACOTE/DEBIAN" \
         "$PACOTE/opt" \
         "$PACOTE/usr/bin" \
         "$PACOTE/usr/share/applications" \
         "$PACOTE/usr/share/icons/hicolor/256x256/apps" \
         "$PACOTE/usr/share/icons/hicolor/scalable/apps" \
         "$PACOTE/usr/lib/udev/rules.d" \
         "$PACOTE/usr/share/doc/meshcore-tracker" \
         "$SAIDA"

cp -r "$RAIZ/dist/meshcore-tracker" "$PACOTE/opt/meshcore-tracker"
ln -s /opt/meshcore-tracker/meshcore-tracker "$PACOTE/usr/bin/meshcore-tracker"
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
Depends: libc6 (>= 2.35), xdg-utils
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
pkill -f /opt/meshcore-tracker/meshcore-tracker || true
exit 0
FIM
chmod 755 "$PACOTE/DEBIAN/prerm"

chmod -R u=rwX,go=rX "$PACOTE/opt" "$PACOTE/usr"
chmod 755 "$PACOTE/opt/meshcore-tracker/meshcore-tracker"
dpkg-deb --root-owner-group --build "$PACOTE" "$SAIDA/MeshcoreTracker-$VERSAO-ubuntu-amd64.deb"
