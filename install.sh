#!/usr/bin/env bash
# Installerer pluginene på en Opsview-server eller collector (Debian/Ubuntu).
# Kjør som root:  sudo ./install.sh
set -euo pipefail
PLUGDIR=${PLUGDIR:-/opt/opsview/monitoringscripts/plugins}
ETCDIR=${ETCDIR:-/opt/opsview/monitoringscripts/etc}
ASCII42_REF=${ASCII42_REF:-main}
cd "$(dirname "$0")"

echo "==> Avhengigheter (curl, jq, gawk, python3)"
apt-get install -y curl jq gawk python3 >/dev/null

echo "==> check_fortigate_health.sh (ascii42, ref: $ASCII42_REF)"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git clone -q --depth 1 --branch "$ASCII42_REF" https://github.com/ascii42/check_fortigate_health.git "$tmp/a42"
install -m 755 "$tmp/a42/check_fortigate_health.sh" "$PLUGDIR/check_fortigate_health.sh"

echo "==> fortigate_opsview.py"
install -m 755 plugins/fortigate_opsview.py "$PLUGDIR/fortigate_opsview.py"

echo "==> Eksempelkonfig for discovery"
mkdir -p "$ETCDIR"
if [[ ! -f "$ETCDIR/fortigate_opsview.ini" ]]; then
  install -m 640 -o opsview -g opsview opsview/fortigate_opsview.ini.example "$ETCDIR/fortigate_opsview.ini"
  echo "    Fyll inn $ETCDIR/fortigate_opsview.ini (Opsview API-bruker)"
else
  echo "    $ETCDIR/fortigate_opsview.ini finnes allerede, ikke endret"
fi
echo "Ferdig. Test:  sudo -u opsview $PLUGDIR/fortigate_opsview.py discovery -H <ip> -T <token> --port 8443 --have \"\""
