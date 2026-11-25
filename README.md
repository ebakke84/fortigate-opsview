# fortigate-opsview

Overvåking av FortiGate, FortiSwitch og FortiAP i Opsview via FortiGate sitt REST-API over WAN, uten IPsec.

- Selve sjekkene gjøres av [ascii42/check_fortigate_health](https://github.com/ascii42/check_fortigate_health).
- Dette repoet legger til `fortigate_opsview.py` (streng modus og discovery), FortiGate-konfig,
  Opsview-oppsett og NOC-prosedyre.

FortiSwitch og FortiAP leses gjennom FortiGate (FortiLink), så de trenger ingen egen tilgang.

## Innhold

| Sti | Hva |
| --- | --- |
| `plugins/fortigate_opsview.py` | `require` (streng modus foran ascii42) og `discovery`. Kun Python 3 standardbibliotek |
| `fortigate/fortigate_monitoring.conf` | CLI-blokk for hver FortiGate: local-in-policy, read-only API-bruker, admin-port |
| `fortigate/fortigate_monitoring.j2` | Samme blokk som Jinja2-mal for config-generatoren (flere WAN-er, ekstra admin-IP-er) |
| `opsview/servicechecks.md` | Variabel, servicechecker og maler i Opsview |
| `opsview/noc-prosedyre.md` | Steg for steg for NOC, og hva som varsles |
| `opsview/fortigate_opsview.ini.example` | Opsview API-bruker for discovery |
| `install.sh` | Installerer pluginene på Opsview-server/collector |
| `tests/run_tests.sh` | Tester mot simulert FortiGate og Opsview |

## Hvorfor to tillegg

ascii42 gir grønt når noe forsvinner (`no managed APs`, HA `standalone`). Derfor:

- **`require`** sjekker at funksjonen finnes når malen ligger på hosten. Mangler den: CRITICAL.
  Finnes den: kjører ascii42 og sender output og exit-kode videre uendret. HA krever minst 2 noder.
- **`discovery`** finner HA, SD-WAN, FortiSwitch og FortiAP på boksen, sammenligner med hostens
  maler i Opsview og varsler om manglende maler og enheter som venter på autorisering.

## Kom i gang

1. **FortiGate:** lim inn `fortigate/fortigate_monitoring.conf` (bytt `<OPSVIEW_IP>`, `wan1`, `8443`), kjør
   `execute api-user generate-key opsview` og ta vare på tokenet.
2. **Test fra Opsview-serveren:**
   `curl -sk -H "Authorization: Bearer <token>" https://<wan-ip>:8443/api/v2/monitor/system/status`
3. **Installer:** `sudo ./install.sh`
4. **Test pluginene manuelt:**
   ```bash
   P=/opt/opsview/monitoringscripts/plugins
   sudo -u opsview $P/check_fortigate_health.sh -H <ip> -T <token> --https-port 8443 -A -v
   sudo -u opsview $P/fortigate_opsview.py discovery -H <ip> -T <token> --port 8443 --have ""
   ```
5. **Opsview:** sett opp variabel, servicechecker og maler etter `opsview/servicechecks.md`.
6. **NOC:** legg inn hoster etter `opsview/noc-prosedyre.md`.

## Bruk

```
fortigate_opsview.py require --feature {ha,sdwan,switch,ap} -H <host> -T <token> [--port 8443]
                             [--min-members 2] [--vdom V] [--sdwan-vdom V] -- <plugin og argumenter>
fortigate_opsview.py discovery -H <host> -T <token> [--port 8443]
                               (--opsview-host $HOSTNAME$ [--opsview-config ini] | --have ha,ap,...)
```

Tokenet kan også gis i miljøvariabelen `FORTIGATE_TOKEN`. Exit-koder: 0 OK, 1 WARNING, 2 CRITICAL, 3 UNKNOWN.

## Begrensninger og ting å verifisere

- Ingen oppetidssjekk: FortiOS 7.4+ gir ikke oppetid via API.
- Opsview-oppslaget (`/rest/login`, `/rest/config/host`) er testet mot simulert API. Verifiser mot egen Opsview.
- Feltene for autorisering (`admin` på FortiAP, `fsw-wan1-admin` på FortiSwitch) er antatt ut fra FortiOS-konfigen.
  Bekreft mot en boks med en uautorisert enhet.
- Sjekk at ascii42 `-eSW`/`-eAP` ikke regner uautoriserte enheter som nede.

## Lisens

MIT. ascii42/check_fortigate_health er MIT-lisensiert og hentes separat av `install.sh`.
