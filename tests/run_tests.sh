#!/usr/bin/env bash
# Tester fortigate_opsview.py mot simulert FortiGate og Opsview. Krever python3 og openssl.
set -u
cd "$(dirname "$0")"
P="python3 ../plugins/fortigate_opsview.py"
TMP=$(mktemp -d); trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$TMP"' EXIT
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$TMP/k.pem" -out "$TMP/c.pem" -days 1 -subj /CN=localhost 2>/dev/null
python3 mock_fortigate.py scenario_standalone.json 9441 "$TMP/c.pem" "$TMP/k.pem" &
python3 mock_fortigate.py scenario_full.json 9442 "$TMP/c.pem" "$TMP/k.pem" &
python3 mock_opsview.py 9443 &
printf "[opsview]\nurl = http://127.0.0.1:9443\nusername = forti-discovery\npassword = pw\n" > "$TMP/ov.ini"
sleep 1
fail=0
check(){ local want=$1 desc=$2; shift 2; out=$("$@" 2>&1); got=$?
  if [[ $got -eq $want ]]; then echo "PASS  $desc"; else echo "FAIL  $desc (forventet $want, fikk $got)"; echo "$out" | sed 's/^/      /'; fail=1; fi; }
check 0 "standalone: discovery uten tillegg = OK"          $P discovery -H 127.0.0.1 --port 9441 -T good --have ""
check 2 "standalone: require ap = CRITICAL"                $P require --feature ap -H 127.0.0.1 --port 9441 -T good -- true
check 2 "standalone: require ha = CRITICAL"                $P require --feature ha -H 127.0.0.1 --port 9441 -T good
check 1 "full: discovery med manglende maler = WARNING"    $P discovery -H 127.0.0.1 --port 9442 -T good --have ha
check 2 "full: HA med 1 av 2 noder = CRITICAL"             $P require --feature ha -H 127.0.0.1 --port 9442 -T good
check 0 "full: require ap sender OK videre"                $P require --feature ap -H 127.0.0.1 --port 9442 -T good -- sh -c 'echo OK; exit 0'
check 2 "full: require switch sender CRITICAL videre"      $P require --feature switch -H 127.0.0.1 --port 9442 -T good -- sh -c 'echo CRIT; exit 2'
check 1 "full: opsview-oppslag, ventende enhet = WARNING"  $P discovery -H 127.0.0.1 --port 9442 -T good --opsview-host fw-x --opsview-config "$TMP/ov.ini"
check 3 "feil token = UNKNOWN"                             $P discovery -H 127.0.0.1 --port 9442 -T bad --have ha
check 3 "ingen kontakt = UNKNOWN"                          $P discovery -H 127.0.0.1 --port 9999 -T good --have ha --timeout 3
exit $fail
