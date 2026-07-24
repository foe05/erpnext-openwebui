# Setup: mcpo per Subdomain hinter Nginx Proxy Manager

Der robuste Weg, den ERPNext-Connector (via mcpo) für OpenWebUI erreichbar und
abgesichert zu machen — über eine eigene Subdomain mit TLS, ohne Pfad-Rewrite.

```
 Browser / OpenWebUI ──HTTPS──▶ Nginx Proxy Manager ──http──▶ 172.17.0.1:8111
   https://tools.broetzens.de/erpnext   (TLS terminiert)        mcpo auf der VM
```

Warum Subdomain statt Pfad: Nginx Proxy Manager ist auf *ein Hostname = ein
Proxy Host* gebaut. Eine Subdomain ist ein Standard-Formular; ein Unterpfad
(`/mcp/…`) braucht Custom-Nginx mit Rewrite und kann an OpenWebUIs URL-Bildung
scheitern. Subdomain = keine Sonderfälle.

## Voraussetzungen

- mcpo läuft auf der VM (siehe README.md) und liefert `.../erpnext/openapi.json`.
- Nginx Proxy Manager terminiert bereits TLS für `chat.broetzens.de`.
- Du kannst DNS für `broetzens.de` verwalten.

## 1. DNS-Eintrag

Einen A-Record anlegen:

```
tools.broetzens.de.   A   <öffentliche-IP-der-VM>
```

(Oder CNAME auf denselben Namen wie `chat.broetzens.de`, falls der auf die VM zeigt.)

## 2. mcpo starten (erreichbar für den NPM-Container + Key)

NPM läuft üblicherweise selbst als Container — `127.0.0.1` wäre dort der
NPM-Container, nicht der Host. Deshalb bindet mcpo auf alle Interfaces (der
öffentliche Port wird später per Firewall zugemacht, Task 5.2) und schützt sich
mit einem API-Key:

```bash
source .venv/bin/activate
mcpo --config deploy/mcpo.config.json --host 0.0.0.0 --port 8111 --api-key "DEIN_GEHEIMER_KEY"
```

Als dauerhaften Dienst später via systemd (Task 5.x). Für den ersten Lauf reicht
das Terminal / tmux.

## 3. Nginx Proxy Manager — neuer Proxy Host

Im NPM-UI **Add Proxy Host**:

- **Details**
  - Domain Names: `tools.broetzens.de`
  - Scheme: `http`
  - Forward Hostname / IP: `172.17.0.1`  (Host aus Container-Sicht; notfalls
    `ip -4 addr show docker0 | grep -oP 'inet \K[\d.]+'` auf dem Host)
  - Forward Port: `8111`
  - Block Common Exploits: an
  - Websockets Support: an (schadet nicht)
- **SSL**
  - SSL Certificate: *Request a new SSL Certificate* (Let's Encrypt)
  - Force SSL: an
  - HTTP/2: an

Speichern. NPM holt das Zertifikat und lädt nginx neu.

## 4. OpenWebUI — externen Tool-Server eintragen

Admin Panel → **Settings → Tools** → externer Tool-Server:

- URL: `https://tools.broetzens.de/erpnext`
- Auth: den `DEIN_GEHEIMER_KEY` als Bearer/API-Key hinterlegen

Läuft der OpenWebUI-Container bei einem anderen User, trägt der das ein — oder du
übers Admin-Panel, falls du dort Zugang hast.

## 5. Verifizieren

1. **Vom eigenen Rechner (Browser):**
   `https://tools.broetzens.de/erpnext/openapi.json` → liefert JSON mit den
   Werkzeugen (`finde_kunde`, `hole`, …). Dann steht der Tunnel inkl. TLS.
2. **Im OpenWebUI-Chat:** `erpnext` in der Eingabezeile aktivieren (Werkzeug-Symbol)
   und z. B. „Finde den Kunden Meier" schreiben. Erwartung: die echte ID kommt
   zurück (oder bei mehreren Treffern die Kandidatenliste).

Kommt der Kunde zurück, ist Phase 0 durch alle vier Hops grün:
OpenWebUI → mcpo → MCP → ERPNext.

## Sicherheit

- **API-Key** (`--api-key`) ist Pflicht, sobald mcpo öffentlich erreichbar ist —
  sonst kann jeder deinen ERPNext-Schreibzugriff nutzen.
- **Port 8111 zumachen:** von außen darf nur 443 (NPM) offen sein. Firewall so
  setzen, dass 8111 nur aus den Docker-Subnetzen erreichbar ist (Task 5.2), z. B.
  `ufw deny 8111`. Der NPM-Container erreicht mcpo weiterhin über die Bridge.
- **TLS** übernimmt NPM (Let's Encrypt) — mcpo selbst spricht nur http intern.

## Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| openapi.json lädt über HTTPS nicht | Forward-IP falsch (nicht `172.17.0.1`) oder mcpo bindet nicht auf 0.0.0.0. Bridge-IP prüfen. |
| 502 Bad Gateway in NPM | mcpo läuft nicht oder Port/IP im Proxy Host falsch. mcpo-Log ansehen. |
| Zertifikat schlägt fehl | DNS zeigt noch nicht auf die VM, oder Port 80 für die LE-Challenge nicht erreichbar. |
| Chat ruft Tool nicht auf | Tool im Chat nicht aktiviert, oder Modell ohne Function-Calling. |
| 401/403 beim Tool-Aufruf | API-Key in OpenWebUI fehlt oder weicht von `--api-key` ab. |
