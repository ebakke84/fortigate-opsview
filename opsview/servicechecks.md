# Opsview: variabel, servicechecker og maler

`P` = `/opt/opsview/monitoringscripts/plugins`

## Variabel

| Variabel | arg1 | arg2 |
| --- | --- | --- |
| `FORTIGATE` | API-token (merk som kryptert/skjult) | Admin-port, f.eks. `8443` |

## Servicechecker

Anbefalt: intervall 5 min, retry 1 min, max check attempts 3. Lisens og Discovery: intervall 1 time.

| Service | Plugin | Argumenter |
| --- | --- | --- |
| FortiGate System | `check_fortigate_health.sh` | `-H $HOSTADDRESS$ -T %FORTIGATE:1% --https-port %FORTIGATE:2% -eSys -eRes -eSensor -eSD` |
| FortiGate Lisens/Sert/Firmware | `check_fortigate_health.sh` | `-H $HOSTADDRESS$ -T %FORTIGATE:1% --https-port %FORTIGATE:2% -eLic -eCert -eFirmware` |
| FortiGate Discovery | `fortigate_opsview.py` | `discovery -H $HOSTADDRESS$ -T %FORTIGATE:1% --port %FORTIGATE:2% --opsview-host $HOSTNAME$` |
| FortiGate HA | `fortigate_opsview.py` | `require --feature ha -H $HOSTADDRESS$ -T %FORTIGATE:1% --port %FORTIGATE:2% -- P/check_fortigate_health.sh -H $HOSTADDRESS$ -T %FORTIGATE:1% --https-port %FORTIGATE:2% -eHA` |
| FortiGate SD-WAN | `fortigate_opsview.py` | Som HA, med `--feature sdwan` og `-eSDWAN` |
| FortiSwitch | `fortigate_opsview.py` | Som HA, med `--feature switch` og `-eSW` |
| FortiAP | `fortigate_opsview.py` | Som HA, med `--feature ap` og `-eAP` |

SD-WAN i annen VDOM: legg til `--sdwan-vdom <navn>` på begge pluginene i SD-WAN-servicen.

## Maler

| Mal | Servicer | Legges på |
| --- | --- | --- |
| FortiGate - Base | System, Lisens/Sert/Firmware, Discovery + host check ping | Alle FortiGate-er |
| FortiGate - HA | FortiGate HA | HA-clustere |
| FortiGate - SD-WAN | FortiGate SD-WAN | Bokser med SD-WAN-SLA |
| FortiGate - FortiSwitch | FortiSwitch | Bokser med FortiLink-switcher |
| FortiGate - FortiAP | FortiAP | Bokser med FortiAP-er |

Malnavnene må matche `[templates]` i `fortigate_opsview.ini`.

## Opsview API-bruker for discovery

Egen bruker (f.eks. `forti-discovery`) med en rolle som kun kan lese konfigurasjon. Legges i
`/opt/opsview/monitoringscripts/etc/fortigate_opsview.ini`. Discovery bruker `POST /rest/login` og
`GET /rest/config/host?json_filter={"name":"<host>"}` for å se hostens maler.
