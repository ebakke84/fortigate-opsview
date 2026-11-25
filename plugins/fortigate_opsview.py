#!/usr/bin/env python3
"""
fortigate_opsview.py - tillegg til check_fortigate_health.sh (ascii42) for Opsview.

To moduser, kun Python 3 standardbibliotek (ingen pip-pakker):

  require   Streng modus. Sjekker at en funksjon (ha, sdwan, switch, ap) faktisk
            finnes på FortiGate-en. Mangler den -> CRITICAL. Finnes den -> kjører
            kommandoen etter "--" (normalt check_fortigate_health.sh) og sender
            output og exit-kode videre uendret.

  discovery Finner hvilke funksjoner boksen har, og sammenligner med hvilke
            Opsview-maler hosten har. Funksjon funnet uten mal -> WARNING.
            Enheter som venter på autorisering (FortiSwitch/FortiAP) -> WARNING.

Exit-koder (Nagios/Opsview): 0 OK, 1 WARNING, 2 CRITICAL, 3 UNKNOWN.

Eksempler:
  fortigate_opsview.py require --feature ap -H fw.example.no -T TOKEN --port 8443 -- \
      /opt/opsview/monitoringscripts/plugins/check_fortigate_health.sh \
      -H fw.example.no -T TOKEN --https-port 8443 -eAP

  fortigate_opsview.py discovery -H fw.example.no -T TOKEN --port 8443 \
      --opsview-host fw-kunde-a --opsview-config /opt/opsview/monitoringscripts/etc/fortigate_opsview.ini

  fortigate_opsview.py discovery -H fw.example.no -T TOKEN --have ha,ap
"""

import argparse
import configparser
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0.0"

OK, WARNING, CRITICAL, UNKNOWN = 0, 1, 2, 3
STATE_NAME = {OK: "OK", WARNING: "WARNING", CRITICAL: "CRITICAL", UNKNOWN: "UNKNOWN"}

FEATURES = ("ha", "sdwan", "switch", "ap")
FEATURE_LABEL = {
    "ha": "HA",
    "sdwan": "SD-WAN",
    "switch": "FortiSwitch",
    "ap": "FortiAP",
}
# Standard malnavn i Opsview. Kan overstyres i ini-fila, seksjon [templates].
DEFAULT_TEMPLATES = {
    "ha": "FortiGate - HA",
    "sdwan": "FortiGate - SD-WAN",
    "switch": "FortiGate - FortiSwitch",
    "ap": "FortiGate - FortiAP",
}


class PluginError(Exception):
    """Feil som skal gi UNKNOWN."""


def finish(state, message, details=None, perf=None):
    line = "%s: %s" % (STATE_NAME[state], message)
    if perf:
        line += " | " + " ".join(perf)
    print(line)
    for d in details or []:
        print(d)
    sys.exit(state)


# --------------------------------------------------------------------------
# FortiGate REST-API
# --------------------------------------------------------------------------
class FortiGate:
    def __init__(self, host, token, port=443, vdom=None, timeout=15,
                 verify=False, ca_bundle=None):
        self.base = "https://%s:%d/api/v2" % (host, port)
        self.token = token
        self.vdom = vdom
        self.timeout = timeout
        if ca_bundle:
            self.ctx = ssl.create_default_context(cafile=ca_bundle)
        elif verify:
            self.ctx = ssl.create_default_context()
        else:
            # FortiGate har normalt selvsignert sertifikat.
            self.ctx = ssl._create_unverified_context()

    def get(self, path, vdom=None, allow_404=False):
        params = {}
        v = vdom or self.vdom
        if v:
            params["vdom"] = v
        url = self.base + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404 and allow_404:
                return None
            if e.code in (401, 403):
                raise PluginError("FortiGate avviste tokenet (HTTP %d) - sjekk token, "
                                  "trusthost og accprofile" % e.code)
            raise PluginError("FortiGate HTTP %d på %s" % (e.code, path))
        except urllib.error.URLError as e:
            raise PluginError("Får ikke kontakt med FortiGate: %s" % e.reason)
        except (ValueError, OSError) as e:
            raise PluginError("Ugyldig svar fra FortiGate på %s: %s" % (path, e))
        return data.get("results")


def as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def detect(fg, sdwan_vdom=None):
    """Returnerer dict med hva boksen har. Ett API-kall per funksjon."""
    found = {}

    # HA: modus fra konfig, antall noder fra statistikk.
    ha_cfg = fg.get("/cmdb/system/ha") or {}
    if isinstance(ha_cfg, list):
        ha_cfg = ha_cfg[0] if ha_cfg else {}
    mode = (ha_cfg.get("mode") or "standalone").lower()
    members = 1
    if mode != "standalone":
        stats = as_list(fg.get("/monitor/system/ha-statistics", allow_404=True))
        members = len(stats) if stats else 1
    found["ha"] = {"present": mode != "standalone", "mode": mode, "members": members}

    # SD-WAN: aktivert i konfig og minst én health-check.
    sd = fg.get("/cmdb/system/sdwan", vdom=sdwan_vdom, allow_404=True) or {}
    if isinstance(sd, list):
        sd = sd[0] if sd else {}
    sd_on = (sd.get("status") or "disable") == "enable"
    hcs = as_list(sd.get("health-check"))
    found["sdwan"] = {"present": sd_on, "health_checks": len(hcs)}

    # FortiSwitch: konfigurerte (autorisert + oppdaget).
    sws = as_list(fg.get("/cmdb/switch-controller/managed-switch", allow_404=True))
    sw_pending = [s.get("switch-id") or s.get("name") or "?" for s in sws
                  if (s.get("fsw-wan1-admin") or "").lower() == "discovered"]
    found["switch"] = {"present": len(sws) > len(sw_pending),
                       "count": len(sws) - len(sw_pending),
                       "pending": sw_pending}

    # FortiAP: konfigurerte WTP-er (aktivert/deaktivert + oppdaget).
    aps = as_list(fg.get("/cmdb/wireless-controller/wtp", allow_404=True))
    ap_pending = [a.get("wtp-id") or a.get("name") or "?" for a in aps
                  if (a.get("admin") or "").lower() == "discovered"]
    found["ap"] = {"present": len(aps) > len(ap_pending),
                   "count": len(aps) - len(ap_pending),
                   "pending": ap_pending}
    return found


# --------------------------------------------------------------------------
# Opsview REST-API (kun lesing) - hvilke maler har hosten?
# --------------------------------------------------------------------------
def opsview_templates(cfg_path, hostname, timeout=15):
    cfg = configparser.ConfigParser()
    if not cfg.read(cfg_path):
        raise PluginError("Finner ikke Opsview-konfig: %s" % cfg_path)
    try:
        url = cfg.get("opsview", "url").rstrip("/")
        user = cfg.get("opsview", "username")
        pw = cfg.get("opsview", "password")
    except (configparser.Error, KeyError) as e:
        raise PluginError("Mangler felt i %s: %s" % (cfg_path, e))
    verify = cfg.getboolean("opsview", "verify_tls", fallback=True)
    ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()

    def call(path, body=None, headers=None):
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url + path, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise PluginError("Opsview API HTTP %d på %s" % (e.code, path))
        except urllib.error.URLError as e:
            raise PluginError("Får ikke kontakt med Opsview API: %s" % e.reason)

    tok = call("/rest/login", {"username": user, "password": pw}).get("token")
    if not tok:
        raise PluginError("Opsview-innlogging ga ikke token")
    auth = {"X-Opsview-Username": user, "X-Opsview-Token": tok}
    flt = urllib.parse.quote(json.dumps({"name": hostname}))
    res = call("/rest/config/host?json_filter=%s" % flt, headers=auth)
    hosts = res.get("list") or []
    if not hosts:
        raise PluginError("Fant ikke host '%s' i Opsview" % hostname)
    names = [t.get("name", "") for t in hosts[0].get("hosttemplates") or []]

    mapping = dict(DEFAULT_TEMPLATES)
    if cfg.has_section("templates"):
        for f in FEATURES:
            mapping[f] = cfg.get("templates", f, fallback=mapping[f])
    have = {f for f in FEATURES if mapping[f] in names}
    return have, mapping


# --------------------------------------------------------------------------
# Moduser
# --------------------------------------------------------------------------
def cmd_require(a, fg):
    found = detect(fg, a.sdwan_vdom)
    f = found[a.feature]
    label = FEATURE_LABEL[a.feature]

    if a.feature == "ha":
        if not f["present"]:
            finish(CRITICAL, "HA forventet, men boksen er standalone",
                   ["Malen '%s' ligger på hosten. Er HA fjernet med vilje, ta av malen."
                    % DEFAULT_TEMPLATES["ha"]])
        if f["members"] < a.min_members:
            finish(CRITICAL, "HA %s: bare %d av %d noder i clusteret"
                   % (f["mode"], f["members"], a.min_members),
                   perf=["ha_members=%d;;%d" % (f["members"], a.min_members)])
    elif not f["present"]:
        hint = {
            "sdwan": "SD-WAN er deaktivert eller ikke konfigurert.",
            "switch": "Ingen autoriserte FortiSwitcher - FortiLink nede eller switcher fjernet?",
            "ap": "Ingen autoriserte FortiAP-er - konfig fjernet eller feil VDOM?",
        }[a.feature]
        finish(CRITICAL, "%s forventet, men ikke funnet" % label,
               [hint, "Malen '%s' ligger på hosten. Er funksjonen fjernet med vilje, ta av malen."
                % DEFAULT_TEMPLATES[a.feature]])

    # Funksjonen finnes -> kjør ascii42-pluginen og send svaret videre.
    if not a.command:
        finish(OK, "%s til stede" % label)
    try:
        p = subprocess.run(a.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=a.cmd_timeout)
    except FileNotFoundError:
        raise PluginError("Finner ikke plugin: %s" % a.command[0])
    except subprocess.TimeoutExpired:
        raise PluginError("Plugin brukte mer enn %ds" % a.cmd_timeout)
    sys.stdout.write(p.stdout.decode("utf-8", "replace"))
    sys.exit(p.returncode if p.returncode in (0, 1, 2, 3) else UNKNOWN)


def cmd_discovery(a, fg):
    found = detect(fg, a.sdwan_vdom)

    if a.have is not None:
        have = {x.strip().lower() for x in a.have.split(",") if x.strip()}
        bad = have - set(FEATURES)
        if bad:
            raise PluginError("Ukjent funksjon i --have: %s" % ",".join(sorted(bad)))
        mapping = DEFAULT_TEMPLATES
    elif a.opsview_host:
        have, mapping = opsview_templates(a.opsview_config, a.opsview_host, a.timeout)
    else:
        raise PluginError("Oppgi --have eller --opsview-host")

    present = [f for f in FEATURES if found[f]["present"]]
    missing = [f for f in present if f not in have]
    state = OK
    lines = []

    for f in present:
        tag = "mal OK" if f in have else "MAL MANGLER: '%s'" % mapping[f]
        extra = ""
        if f == "ha":
            extra = " (%s, %d noder)" % (found[f]["mode"], found[f]["members"])
        elif f in ("switch", "ap"):
            extra = " (%d stk)" % found[f]["count"]
        lines.append("%s funnet%s - %s" % (FEATURE_LABEL[f], extra, tag))

    pending = []
    for f in ("switch", "ap"):
        for dev in found[f]["pending"]:
            pending.append("%s %s venter på autorisering" % (FEATURE_LABEL[f], dev))
    lines.extend(pending)

    if missing:
        state = WARNING
        names = [FEATURE_LABEL[f] for f in missing]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " og " + names[-1]
        msg = "%s funnet, men mal mangler: %s" % (
            joined,
            ", ".join("'%s'" % mapping[f] for f in missing))
    elif pending:
        state = WARNING
        msg = "%d enhet(er) venter på autorisering i FortiGate" % len(pending)
    elif present:
        msg = "alle maler på plass (%s)" % ", ".join(FEATURE_LABEL[f] for f in present)
    else:
        msg = "ingen tillegg funnet (ingen HA, SD-WAN, FortiSwitch eller FortiAP)"

    perf = ["missing_templates=%d;1;" % len(missing),
            "pending_devices=%d;1;" % len(pending)]
    finish(state, msg, lines, perf)


def main():
    p = argparse.ArgumentParser(description="Tillegg til check_fortigate_health for Opsview")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="mode")

    def common(sp):
        sp.add_argument("-H", "--host", required=True, help="FortiGate WAN-IP eller DNS-navn")
        sp.add_argument("-T", "--token", default=os.environ.get("FORTIGATE_TOKEN"),
                        help="API-token (eller miljøvariabel FORTIGATE_TOKEN)")
        sp.add_argument("--port", type=int, default=443, help="HTTPS admin-port (standard 443)")
        sp.add_argument("--vdom", default=None, help="VDOM for API-kall (standard: tokenets VDOM)")
        sp.add_argument("--sdwan-vdom", default=None, help="VDOM der SD-WAN er konfigurert")
        sp.add_argument("--timeout", type=int, default=15, help="Timeout per API-kall i sekunder")
        sp.add_argument("--https-verify", action="store_true", help="Krev gyldig sertifikat")
        sp.add_argument("--ca-bundle", default=None, help="CA-fil for sertifikatsjekk")

    r = sub.add_parser("require", help="Streng modus: funksjonen må finnes")
    common(r)
    r.add_argument("--feature", required=True, choices=FEATURES)
    r.add_argument("--min-members", type=int, default=2, help="Minste antall HA-noder (standard 2)")
    r.add_argument("--cmd-timeout", type=int, default=50, help="Maks tid for pluginen etter --")
    r.add_argument("command", nargs=argparse.REMAINDER,
                   help="-- etterfulgt av pluginen som skal kjøres når funksjonen finnes")

    d = sub.add_parser("discovery", help="Finn funksjoner og sammenlign med Opsview-maler")
    common(d)
    d.add_argument("--have", default=None,
                   help="Kommaliste over maler hosten har (ha,sdwan,switch,ap). Alternativ til Opsview-oppslag")
    d.add_argument("--opsview-host", default=None, help="Hostnavn i Opsview (bruk $HOSTNAME$)")
    d.add_argument("--opsview-config",
                   default="/opt/opsview/monitoringscripts/etc/fortigate_opsview.ini",
                   help="Ini-fil med Opsview API-bruker")

    a = p.parse_args()
    if not a.mode:
        p.print_help()
        sys.exit(UNKNOWN)
    if not a.token:
        finish(UNKNOWN, "Mangler API-token (-T eller FORTIGATE_TOKEN)")
    if a.mode == "require" and a.command and a.command[0] == "--":
        a.command = a.command[1:]

    fg = FortiGate(a.host, a.token, a.port, a.vdom, a.timeout, a.https_verify, a.ca_bundle)
    try:
        if a.mode == "require":
            cmd_require(a, fg)
        else:
            cmd_discovery(a, fg)
    except PluginError as e:
        finish(UNKNOWN, str(e))


if __name__ == "__main__":
    main()
