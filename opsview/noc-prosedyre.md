# NOC: legge til en FortiGate i Opsview

Forutsetning: FortiGate-en har fått monitoreringsblokken (`fortigate/fortigate_monitoring.conf`) og du har API-tokenet.

1. Opprett hosten: navn (f.eks. `fw-kunde-sted`), WAN-IP eller DDNS-navn, riktig collector.
2. Variables: legg til `FORTIGATE` med tokenet i arg1 og admin-porten i arg2.
3. Legg på malen **FortiGate - Base** og kjør Apply Changes.
4. Vent på Discovery (eller Recheck). Gul betyr at maler mangler, f.eks.
   `WARNING: HA og FortiAP funnet, men mal mangler: 'FortiGate - HA', 'FortiGate - FortiAP'`.
5. Legg på malene Discovery nevner, kjør Apply Changes. Discovery blir grønn ved neste kjøring.

Nye AP-er og switcher på en eksisterende site blir med automatisk.

## Varsling

| Tilstand | Når |
| --- | --- |
| CRITICAL | FortiAP eller FortiSwitch nede |
| CRITICAL | HA-malen ligger på, men boksen er standalone eller har under 2 noder, eller HA er ute av synk |
| CRITICAL | Malen ligger på, men funksjonen finnes ikke lenger (FortiLink nede, konfig fjernet) |
| WARNING/CRITICAL | SD-WAN tap/latency, CPU/minne/disk/sensor, lisens/sertifikat utløper |
| WARNING | Discovery: funksjon uten mal, eller enhet venter på autorisering |
| UNKNOWN | API svarer ikke eller token avvises |
| Host DOWN | Ping mot WAN feiler, servicene undertrykkes |

Ikke varsel: deaktiverte eller slettede enheter, antall klienter, switchporter.
Er en funksjon fjernet med vilje: ta av malen. Firmwareoppgradering: sett nedetid på hosten.
