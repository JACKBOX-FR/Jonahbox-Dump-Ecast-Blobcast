# Jonahbox (version Windows) : jouer à Jackbox sans les serveurs officiels

Serveur privé écrit en Rust qui remplace les serveurs de Jackbox Games (ecast / blobcast) pour
que **tes jeux Jackbox achetés sur Steam** continuent de fonctionner sur ton réseau local, même
si les serveurs officiels ferment.

> **Ce projet n'est ni lié à Jackbox Games, Inc., ni approuvé par eux.** Il faut posséder les jeux.
> Il prolonge le travail de [InvoxiPlayGames (johnbox)](https://github.com/InvoxiPlayGames/johnbox)
> et de [StratusFearMe21 (jonahbox)](https://github.com/StratusFearMe21/jonahbox).

---

## 1. Comment ça marche

```
   Téléphones / navigateurs  ──►  https://jonahbox.local  ◄──  Jeu Jackbox (Steam)
        (les manettes)                     │
                                      JONAHBOX (ton PC)
                       ┌──────────────────┴───────────────────┐
                  ecast / blobcast                     cache de la manette
              (salles, joueurs, votes)             (pages web de jackbox.tv)
```

Il y a **trois choses** à faire fonctionner :

| Élément | Rôle | Fourni par |
|---|---|---|
| **Ecast / blobcast** | La logique de la partie (salles, réponses, scores) | Jonahbox (déjà intégré) |
| **La manette** | Une page web que les joueurs ouvrent sur leur téléphone | Le **cache** `jb_cache`, à remplir |
| **Le jeu** | Le jeu Steam | Ton PC, après modification de `jbg.config.jet` |

> Le jeu et les téléphones doivent parler à Jonahbox en **HTTPS** avec un certificat que
> chacun accepte. C'est l'étape qui pose le plus de problèmes : ne la saute pas.

---

## 2. Ce qui est testé

- Testé par l'auteur d'origine : Party Pack 2 à 10, Drawful 2 International.
- Testé sur Windows avec ce dépôt : **Tee K.O. 2 (Party Pack 10)**, salle créée, manette chargée.
- **Party Pack 11 et jeux plus récents : non testés.**
- **Party Pack 1 : expérimental, non testé.** Il ignore `jbg.config.jet` ; on tente de le rediriger
  avec le fichier hosts du PC (§3.4) et un certificat qui couvre les noms `blobcast`.
- **Anciens packs (blobcast) : non testés ici** (redirection des adresses blobcast vers `jonahbox.local` par `dump_to_cache.py`).
- Non implémenté : mots de passe de salle, modération, audience partielle selon les packs.

---

## 3. Installation sur Windows (pas à pas)

### 3.1 Prérequis

- [Rust](https://rustup.rs) (avec les outils de compilation Visual Studio proposés à l'installation)
- [mkcert](https://github.com/FiloSottile/mkcert/releases) (télécharge `mkcert-…-windows-amd64.exe`, renomme-le `mkcert.exe`)
- Python 3 (pour les scripts de cache)
- Les jeux Jackbox sur Steam, et ce dépôt téléchargé et décompressé

Dans la suite, remplace `192.168.68.54` par **l'adresse IPv4 de ton PC** (commande `ipconfig`, ligne « Adresse IPv4 »).

### 3.2 Compiler

Ce dépôt contient déjà les correctifs pour Windows. Si tu pars du dépôt d'origine, applique-les d'abord :

```powershell
git apply windows.patch
```

Dans `src\main.rs`, vérifie aussi que cette ligne existe à côté de la route `/api/v2/rooms` (nécessaire pour que la manette trouve la salle) :

```rust
.route("/api/v2/rooms/{code}", get(ecast::rooms_get_handler))
```

Puis compile :

```powershell
cargo build --release
```

### 3.3 Certificat HTTPS (mkcert)

Dans PowerShell **en administrateur**, dans le dossier `certs` du projet :

```powershell
.\mkcert.exe -install
.\mkcert.exe 192.168.68.54 jonahbox.local blobcast.jackboxgames.com blobcast-test.jackboxgames.com
```

Cela crée deux fichiers `.pem` (le certificat et sa clé : `192.168.68.54+3.pem` et `192.168.68.54+3-key.pem`).
Le certificat couvre **l'IP, le nom `jonahbox.local`, et les noms `blobcast`** (ces deux derniers ne servent qu'au Party Pack 1, voir §3.4).

> **Pourquoi un nom et pas seulement l'IP ?** Chrome accepte les certificats liés à une IP, mais
> le jeu, lui, refuse de se connecter dans ce cas (il reste bloqué sur le chargement).
> Avec un nom (`jonahbox.local`), ça passe.

### 3.4 Fichier hosts du PC

Ouvre le Bloc-notes **en administrateur**, ouvre `C:\Windows\System32\drivers\etc\hosts` et ajoute :

```
192.168.68.54 jonahbox.local
```

Vérifie : `ping jonahbox.local` doit répondre depuis ton IP.

**Party Pack 1 (expérimental)** : ce jeu ignore `jbg.config.jet` et appelle directement
`blobcast.jackboxgames.com`. Pour le forcer vers ton serveur, ajoute aussi dans le **même fichier hosts du PC** :

```
192.168.68.54 blobcast.jackboxgames.com
192.168.68.54 blobcast-test.jackboxgames.com
```

(Un fichier hosts associe un nom à une **adresse IP**, d'où l'IP de ton PC et non `jonahbox.local`.)
Ces deux lignes se mettent **sur le PC qui fait tourner le jeu**, pas sur les téléphones : les
fichiers de la manette ont déjà été réécrits par `dump_to_cache.py`. Cette méthode n'a pas été
validée, voir §2. Pour retrouver les serveurs officiels, supprime simplement ces deux lignes.

### 3.5 Configuration (`config.toml`)

```toml
accessible_host = "jonahbox.local"
tui = true

[cache]
cache_path = "jb_cache"
cache_mode = "oneshot"      # "offline" une fois le cache complet (voir §4)

[ecast]
op_mode = "native"

[blobcast]
op_mode = "native"

[tls]
cert = "C:\\chemin\\vers\\certs\\192.168.68.54+3.pem"
key  = "C:\\chemin\\vers\\certs\\192.168.68.54+3-key.pem"

[ports]
https = 443
blobcast = 38203
http = 80
```

> Les jeux se connectent aux ports **443 et 80** (ecast) et **38203** (blobcast, anciens packs).
> Les valeurs 4343 et 8080 du dépôt d'origine ne conviennent pas à Windows.

### 3.6 Configuration du jeu (`jbg.config.jet`)

Dans le dossier de **chaque** jeu (Steam → Gérer → Parcourir les fichiers locaux), modifie :

```json
"serverUrl": "jonahbox.local",
"joinUrl": "jonahbox.local",
```

Pas de `http://` et **pas de port**.

### 3.7 Pare-feu et redirection de ports

Sur le PC, dans PowerShell **en administrateur** :

```powershell
netsh advfirewall firewall add rule name="Jonahbox" dir=in action=allow protocol=TCP localport=443,80,38203
netsh interface portproxy add v4tov6 listenaddress=192.168.68.54 listenport=443 connectaddress=::1 connectport=443
netsh interface portproxy add v4tov6 listenaddress=192.168.68.54 listenport=80 connectaddress=::1 connectport=80
netsh interface portproxy add v4tov6 listenaddress=192.168.68.54 listenport=38203 connectaddress=::1 connectport=38203
```

- La **règle de pare-feu** autorise les appareils de **ton réseau local** à joindre Jonahbox.
  Sans elle, les navigateurs affichent `ERR_TIMED_OUT`.
- Les **redirections `portproxy`** sont nécessaires car Jonahbox écoute en IPv6 seulement sur
  Windows, alors que le jeu et les téléphones se connectent en IPv4.
- **N'ouvre aucun port sur ta box / ton routeur** : tout reste sur ton réseau local.

---

## 4. Le cache de la manette (à faire tant que les serveurs officiels existent)

La page de la manette est hébergée par Jackbox. Jonahbox la copie dans `jb_cache` à la première
demande. **Si le cache est incomplet le jour où les serveurs ferment, la manette ne s'affichera pas.**

### Option A : laisser Jonahbox remplir le cache (recommandé)

1. `cache_mode = "oneshot"` et PC connecté à internet.
2. Lance Jonahbox, puis fais **une partie complète de chaque jeu** avec un téléphone.
3. Pour les jeux Dodo Re Mi, Junktopia et Time Jinx, lance en plus les scripts `update_*.sh`
   (voir le README d'origine : ils demandent `find`, `jq`, `parallel`, `curl`, donc Git Bash ou WSL).

### Option B : partir du dump `jackbox.tv`

Le dépôt [jackbox-fr-main-dump](https://github.com/JACKBOX-FR/jackbox-fr-main-dump) contient une copie
(traduite en français) de la manette de chaque pack.

1. Télécharge le dump (bouton **Code → Download ZIP**) et décompresse-le.
2. Convertis-le en cache :

   ```powershell
   python dump_to_cache.py --dump C:\chemin\jackbox-fr-main-dump --cache jb_cache
   ```

   Le script **redirige automatiquement** `ecast.jackboxgames.com`, `blobcast.jackboxgames.com`
   et `blobcast-test.jackboxgames.com` vers `jonahbox.local` (changeable avec `--host`,
   désactivable avec `--no-rewrite`). Il n'écrase pas les entrées déjà présentes (`--force` pour le faire).
3. Les fichiers du dump viennent d'une autre version de la manette que celle d'aujourd'hui.
   En cas de comportement étrange, supprime `jb_cache` et utilise l'option A.

> ⚠ Ne copie jamais des fichiers à la main dans `jb_cache` : Jonahbox attend, pour chaque
> ressource, une petite fiche JSON plus le contenu. Si tu as l'erreur
> `could not be deserialized`, supprime le dossier (`rmdir /s /q jb_cache`) et recommence.

### Passer en mode hors ligne

Quand le cache est complet : `cache_mode = "offline"`, coupe internet, et fais une partie de test.
Chaque fichier manquant apparaît dans les logs (« offline resource could not be found »).

---

## 5. Lancer une partie

1. Ouvre PowerShell **en administrateur** dans le dossier du projet.
2. `cargo run --release` (ou `.\target\release\jonahbox.exe`). Vérifie les lignes
   `Ecast listening on [::]:443` et `Blobcast listening on [::]:38203`.
3. Lance le jeu depuis Steam et crée une salle : un **code à 4 lettres** s'affiche.
4. Les joueurs ouvrent `https://jonahbox.local` sur leur appareil, entrent le code et leur nom.

### Rejoindre depuis un téléphone

Le téléphone doit pouvoir résoudre `jonahbox.local` et faire confiance au certificat.

**Résolution du nom, au choix :**
- **Routeur** (le plus simple) : ajoute un enregistrement DNS local `jonahbox.local → 192.168.68.54`
  (cherche « DNS local » ou « hôtes statiques » dans l'interface de ta box).
- **Application « hosts » sur Android** : installe depuis le Play Store une application qui édite le
  fichier hosts via un VPN local (par exemple **Virtual Hosts**, vérifie le nom exact sur le Play Store)
  et ajoute :
  ```
  192.168.68.54  jonahbox.local
  ```
- **Sans rien de tout ça** : remplace `accessible_host` par l'IP du PC. Mais le jeu risque alors de
  refuser la connexion (voir 3.3), donc teste d'abord.

**Certificat :** installe sur le téléphone le certificat racine de mkcert
(`mkcert -CAROOT` donne le dossier, fichier `rootCA.pem`). Sinon le navigateur affiche un
avertissement, que tu peux passer avec « Avancé → Continuer », mais certaines fonctions peuvent ne pas marcher.

---

## 6. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ERR_TIMED_OUT` dans le navigateur | Pare-feu | Règle du §3.7 |
| `ERR_CONNECTION_REFUSED` | Jonahbox n'écoute pas sur 443 | Vérifier `[ports]`, relancer en administrateur, `netstat -ano \| findstr :443` |
| Le jeu reste sur « chargement » après la création de la salle | Certificat lié à une IP seulement | Régénérer avec `mkcert IP jonahbox.local` et utiliser le nom (§3.3 à 3.6) |
| `Salle introuvable` sur la manette | Route `/api/v2/rooms/{code}` absente, ou adresses mal redirigées | Ajouter la ligne du §3.2 ; sinon vider `jb_cache` |
| `could not be deserialized` | Fichier copié à la main dans `jb_cache` | `rmdir /s /q jb_cache` |
| Erreurs `Interest::PRIORITY` à la compilation | Code réservé à Linux | Appliquer `windows.patch` |
| Page de manette blanche | Cache incomplet ou fichiers d'une autre version | Option A du §4 |
| Party Pack 1 ne se connecte pas | Hosts ou certificat sans les noms `blobcast`, ou port 38202/843 non servi | Vérifier §3.3 et §3.4 ; regarder dans les logs si des requêtes `/room` arrivent |
| Un port est déjà utilisé | Autre programme sur 443/80 | `netstat -ano \| findstr :443`, fermer le programme |

---

## 7. TTS (Mad Verse City, FixyText)

Ces jeux ont besoin d'un service de synthèse vocale. En mode `native`, installe
[piper](https://github.com/rhasspy/piper), télécharge des [voix](https://github.com/rhasspy/piper/blob/master/VOICES.md)
dans `voices_path` (config nommée `{voix}.onnx.json`), et installe [ffmpeg](https://ffmpeg.org/).

---

## 8. Pour les curieux : capturer le trafic officiel

Pour étudier le fonctionnement des jeux (ou ajouter la prise en charge d'un nouveau pack), on peut
enregistrer le trafic avec [mitmproxy](https://mitmproxy.org/). Les outils sont dans le dossier
**`jackbox-capture`** :

- `capture2.py` : enregistre le trafic Jackbox (HTTP et WebSocket) dans `captures\session-….jsonl`.
- `viewer.py` : permet de visualiser plus facilement les étapes d'une capture.

```powershell
cd jackbox-capture
mitmdump -s capture2.py                              # trafic des manettes (navigateur)
python viewer.py captures\session-XXXX.jsonl         # visualiser les étapes
python capture2.py captures\session-XXXX.jsonl       # résumé texte compact
```

Pour capturer le **jeu** lui-même, voir l'en-tête de `capture2.py` (mode reverse avec `JB_PROXY_HOST`).

---

## Crédits

- [InvoxiPlayGames / johnbox](https://github.com/InvoxiPlayGames/johnbox)
- [StratusFearMe21 / jonahbox](https://github.com/StratusFearMe21/jonahbox)
- [JACKBOX-FR / jackbox-fr-main-dump](https://github.com/JACKBOX-FR/jackbox-fr-main-dump)
