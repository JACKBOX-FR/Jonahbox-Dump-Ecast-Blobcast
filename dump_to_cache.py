#!/usr/bin/env python3
"""
Injecte les fichiers du dump jackbox.tv dans le cache de Jonahbox (aucun internet requis)
et redirige au passage les adresses ecast / blobcast vers votre serveur.

Format de cache de Jonahbox, pour une URL https://H/P :
  - jb_cache/H/P        -> petit JSON {"etag", "content_type", "compressed"}
  - jb_cache/H/<etag>   -> le contenu du fichier (non compressé)

USAGE
  python dump_to_cache.py --dump C:\\chemin\\jackbox-fr-main-dump --cache jb_cache

OPTIONS
  --host jonahbox.local   nom (ou IP) qui remplace ecast / blobcast dans les fichiers texte
  --no-rewrite            ne modifie aucun fichier (copie brute)
  --extra-host NOM        autre domaine à rediriger (répétable)
  --force                 écrase les entrées déjà présentes dans le cache
  --prefix /main          préfixe d'URL du dossier 'main' du dump

Les fichiers du dossier 'main' sont rangés sous https://jackbox.tv<prefix>/...
Les fichiers à la racine du dump (index.html, ...) sont rangés à la racine.
"""
import argparse, hashlib, json, mimetypes, os, re, shutil

HOST = "jackbox.tv"
TEXT_EXT = {".js", ".mjs", ".html", ".htm", ".css", ".json", ".webmanifest", ".txt", ".jet"}
DEFAULT_REWRITE = ["ecast.jackboxgames.com", "blobcast.jackboxgames.com",
                   "blobcast-test.jackboxgames.com"]


def build_rewriter(new_host, domains):
    if not new_host or not domains:
        return None
    pattern = re.compile("|".join(re.escape(d) for d in sorted(domains, key=len, reverse=True)))
    new = new_host.encode()
    pat = re.compile(pattern.pattern.encode())
    return lambda data: pat.subn(new, data)


def add(cache, url_path, src, rewrite, force, stats):
    key = os.path.join(cache, HOST, "index.html" if url_path == "/" else url_path.lstrip("/"))
    if os.path.exists(key) and not force:
        stats["skipped"] += 1
        return
    with open(src, "rb") as f:
        data = f.read()
    if rewrite and os.path.splitext(src)[1].lower() in TEXT_EXT:
        data, n = rewrite(data)
        if n:
            stats["rewritten_files"] += 1
            stats["rewritten_refs"] += n
    etag = "dump-" + hashlib.sha1(data).hexdigest()
    blob = os.path.join(cache, HOST, etag)
    os.makedirs(os.path.dirname(key), exist_ok=True)
    if not os.path.exists(blob):
        with open(blob, "wb") as f:
            f.write(data)
    ctype = mimetypes.guess_type(src)[0] or "application/octet-stream"
    with open(key, "w") as f:
        json.dump({"etag": etag, "content_type": ctype, "compressed": False}, f)
    stats["added"] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--cache", default="jb_cache")
    ap.add_argument("--prefix", default="/main")
    ap.add_argument("--host", default="jonahbox.local")
    ap.add_argument("--no-rewrite", action="store_true")
    ap.add_argument("--extra-host", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    rewrite = None if a.no_rewrite else build_rewriter(a.host, DEFAULT_REWRITE + a.extra_host)
    stats = {"added": 0, "skipped": 0, "rewritten_files": 0, "rewritten_refs": 0}

    root_main = os.path.join(a.dump, "main")
    for dp, _, files in os.walk(root_main):
        for f in files:
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, root_main).replace(os.sep, "/")
            add(a.cache, f"{a.prefix}/{rel}", src, rewrite, a.force, stats)
    for f in os.listdir(a.dump):
        src = os.path.join(a.dump, f)
        if os.path.isfile(src) and f not in ("README.md", "CNAME", "LICENSE"):
            add(a.cache, "/" if f == "index.html" else f"/{f}", src, rewrite, a.force, stats)

    print(f"{stats['added']} entrées ajoutées, {stats['skipped']} déjà présentes (ignorées)")
    if rewrite:
        print(f"{stats['rewritten_refs']} adresses redirigées vers {a.host} "
              f"dans {stats['rewritten_files']} fichiers")


if __name__ == "__main__":
    main()
