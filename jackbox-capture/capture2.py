"""
capture2.py - capture compacte du trafic Jackbox pour mitmproxy / mitmdump.

Différences avec capture.py :
  - ne garde que les domaines jackbox (le reste est ignoré)
  - images / polices / JS / CSS : on note seulement url, statut, taille (pas le contenu)
  - les corps JSON / texte sont décodés (gzip, br) et tronqués à 20 000 caractères
  - WebSocket : les deux sens, numérotés, avec un identifiant de connexion
  - un fichier par session : captures/session-<date>.jsonl
  - mode "jeu" (optionnel) : réécrit le champ `host` renvoyé par ecast pour que le JEU
    (et pas seulement la manette) passe par mitmproxy -> voir variable JB_PROXY_HOST

USAGE (manette, mode normal, comme avant) :
  mitmdump -s capture2.py

USAGE (jeu, mode reverse) :
  set JB_PROXY_HOST=192.168.68.54
  mitmdump --mode reverse:https://ecast.jackboxgames.com --listen-host 0.0.0.0 --listen-port 443 -s capture2.py

RÉSUMÉ LISIBLE (à me coller dans la conversation, quelques Ko) :
  python capture2.py captures/session-XXXX.jsonl
"""
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

OUT_DIR = Path("captures")
OUT_FILE = OUT_DIR / time.strftime("session-%Y%m%d-%H%M%S.jsonl")
MAX_TEXT = 20000
PROXY_HOST = os.environ.get("JB_PROXY_HOST", "").strip()

STATIC_RE = re.compile(r"\.(png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf|mp3|ogg|wav|mp4|webm|usm|js|css|map)(\?|$)", re.I)
ROOM_RE = re.compile(r"^/api/v2/(?:rooms|audience)/([A-Z]{4})(?:/|$|\?)")

real_hosts = {}   # code de salle -> vrai host ecast (ex. ecast-prod-use2...)
ws_ids = {}       # id de flow -> numéro de connexion
t0 = time.time()


def is_jb(host):
    return bool(host) and "jackbox" in host


def write(rec):
    OUT_DIR.mkdir(exist_ok=True)
    rec["t"] = round(time.time() - t0, 3)
    with OUT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def body_info(msg, ctype):
    """Résumé du corps : texte décodé si utile, sinon taille + hash."""
    raw = msg.raw_content or b""
    info = {"size": len(raw)}
    if not raw:
        return info
    path_static = False
    try:
        path_static = bool(STATIC_RE.search(msg.path))
    except Exception:
        pass
    texty = any(k in (ctype or "") for k in ("json", "text/plain", "xml", "html"))
    if texty and not path_static:
        try:
            txt = msg.get_text(strict=False) or ""
            info["text"] = txt[:MAX_TEXT]
            if len(txt) > MAX_TEXT:
                info["truncated"] = len(txt)
            return info
        except Exception:
            pass
    try:
        info["sha1"] = hashlib.sha1(msg.get_content(strict=False) or raw).hexdigest()[:12]
    except Exception:
        pass
    return info


# ---------- HTTP ----------

def request(flow):
    req = flow.request
    if not is_jb(req.host):
        return
    # Mode jeu : envoyer les WebSocket vers le vrai serveur de la salle
    if PROXY_HOST:
        m = ROOM_RE.match(req.path)
        if m and m.group(1) in real_hosts and "/play" in req.path:
            real = real_hosts[m.group(1)]
            req.host, req.port, req.scheme = real, 443, "https"
            req.headers["Host"] = real
    write({
        "type": "req", "id": flow.id[:8], "method": req.method,
        "host": req.host, "path": req.path[:300],
        "body": body_info(req, req.headers.get("content-type", "")) if req.raw_content else None,
    })


def response(flow):
    req, res = flow.request, flow.response
    if not is_jb(req.host):
        return
    ctype = res.headers.get("content-type", "")
    # Mode jeu : réécrire host / audienceHost pour que le jeu revienne chez nous
    if PROXY_HOST and "json" in ctype and ROOM_RE.match(req.path) is None and req.path.startswith("/api/v2/rooms"):
        try:
            data = json.loads(res.get_text(strict=False))
            body = data.get("body", {})
            if "code" in body and "host" in body:
                real_hosts[body["code"]] = body["host"]
                body["host"] = PROXY_HOST
                body["audienceHost"] = PROXY_HOST
                res.text = json.dumps(data)
        except Exception as e:
            write({"type": "note", "msg": f"réécriture host impossible: {e}"})
    if PROXY_HOST and "json" in ctype and ROOM_RE.match(req.path):
        try:
            data = json.loads(res.get_text(strict=False))
            body = data.get("body", {})
            if "host" in body:
                real_hosts[body.get("code", "")] = body["host"]
                body["host"] = PROXY_HOST
                body["audienceHost"] = PROXY_HOST
                res.text = json.dumps(data)
        except Exception:
            pass
    write({
        "type": "res", "id": flow.id[:8], "status": res.status_code,
        "host": req.host, "path": req.path[:300],
        "body": body_info(res, ctype),
    })


# ---------- WebSocket ----------

def websocket_message(flow):
    if not is_jb(flow.request.host) or not flow.websocket:
        return
    n = ws_ids.setdefault(flow.id, len(ws_ids) + 1)
    msg = flow.websocket.messages[-1]
    c = msg.content
    rec = {
        "type": "ws", "conn": n, "path": flow.request.path[:200],
        "dir": "C>S" if msg.from_client else "S>C",
    }
    try:
        rec["text"] = (c.decode("utf-8") if isinstance(c, bytes) else str(c))[:MAX_TEXT]
    except UnicodeDecodeError:
        rec["b64"] = base64.b64encode(c[:3000]).decode()
        rec["size"] = len(c)
    write(rec)


def error(flow):
    if flow.error and flow.request and is_jb(flow.request.host):
        write({"type": "error", "host": flow.request.host,
               "path": flow.request.path[:200], "error": str(flow.error)})


def tls_failed_client(data):
    """Appelé quand un client refuse notre certificat : essentiel pour le jeu."""
    write({"type": "tls_failed", "client": str(data.context.client.peername),
           "sni": data.context.client.sni, "error": str(data.conn.error)})


# ---------- Résumé compact : python capture2.py fichier.jsonl ----------

def summarize(path):
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        t = r.get("t", 0)
        k = r["type"]
        if k == "req":
            print(f"{t:7.2f} > {r['method']} {r['host']}{r['path'][:110]}")
        elif k == "res":
            b = r["body"]
            txt = (b.get("text") or "")[:160].replace("\n", " ")
            print(f"{t:7.2f} < {r['status']} {r['path'][:70]} [{b.get('size')}o] {txt}")
        elif k == "ws":
            print(f"{t:7.2f} WS{r['conn']} {r['dir']} {(r.get('text') or '<bin>')[:300]}")
        else:
            print(f"{t:7.2f} {k.upper()} {r}")


if __name__ == "__main__":
    summarize(sys.argv[1])
