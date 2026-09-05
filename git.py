#!/usr/bin/env python3
"""
GitHub File Manager Script (esteso)
Mantiene tutte le funzionalità originali (creare/aggiornare/eliminare/leggere/upload batch/upload da directory)
e aggiunge:
 - Interfaccia a riga di comando (subcommand) per operare non interattivamente
 - Supporto per file binari (lettura/scrittura base64)
 - Download di file dal repository su disco locale
 - Lista del contenuto di una directory remota nel repo
 - Creazione di un nuovo branch (da base branch o default branch)
 - Recupero della storia dei commit per un file
 - Logging opzionale su file
 - Modalità "dry-run" per batch/upload-from-dir
Tutte le funzioni originali mantengono le loro firme e comportamento.
"""
from __future__ import annotations

import os
import json
import sys
import argparse
import base64
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

try:
    import requests
except ImportError:
    print("Errore: 'requests' non è installato.")
    print("Installa con: pip install requests")
    sys.exit(1)


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback se il terminale non supporta alcuni caratteri
        encoded = " ".join(str(a).encode("utf-8", errors="replace").decode("utf-8") for a in args)
        print(encoded, **{k: v for k, v in kwargs.items() if k != "flush"})


class GitHubFileManager:
    """Gestisce file su GitHub via API REST (esteso)"""

    def __init__(self, owner: str, repo: str, token: str, branch: str = "main", log_file: Optional[str] = None):
        """
        Inizializza il manager GitHub.

        Args:
            owner: Proprietario del repository
            repo: Nome del repository
            token: Token di autenticazione GitHub (Personal Access Token)
            branch: Ramo su cui operare (default: main)
            log_file: Percorso opzionale per scrivere un log delle operazioni
        """
        self.owner = owner
        self.repo = repo
        self.token = token
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.log_file = log_file
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"--- New session started at {time.asctime()} ---\n")
            except Exception:
                pass

    def _log(self, message: str):
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"{time.asctime()}: {message}\n")
            except Exception:
                pass

    # ---------- Helpers ----------
    @staticmethod
    def _is_binary_bytes(data: bytes) -> bool:
        # Semplice heuristica: presenza di null bytes o sequenze non-utf8 comuni
        if not data:
            return False
        if b'\x00' in data:
            return True
        try:
            data.decode('utf-8')
            return False
        except UnicodeDecodeError:
            return True

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        # wrapper per loggare richieste
        self._log(f"HTTP {method} {url} payload_keys={list(kwargs.keys())}")
        response = requests.request(method, url, headers=self.headers, **kwargs)
        self._log(f"RESPONSE {response.status_code} {response.reason}")
        return response

    # ---------- Existing methods (kept behavior) ----------
    def get_file_sha(self, file_path: str) -> Optional[str]:
        """
        Ottiene lo SHA blob del file se esiste.
        """
        try:
            url = f"{self.base_url}/contents/{file_path}"
            params = {"ref": self.branch}
            response = self._request("GET", url, params=params)
            if response.status_code == 200:
                return response.json().get("sha")
            elif response.status_code == 404:
                return None
            else:
                safe_print(f"Errore nel recupero dello SHA: {response.status_code}")
                safe_print(response.text)
                return None
        except requests.RequestException as e:
            safe_print(f"Errore di connessione: {e}")
            return None

    def read_file(self, file_path: str) -> Optional[str]:
        """
        Legge il contenuto di un file dal repository e lo ritorna come stringa (utf-8).
        Se il file è binario, prova a decodificare; in caso di fallimento ritorna None.
        """
        try:
            url = f"{self.base_url}/contents/{file_path}"
            params = {"ref": self.branch}
            response = self._request("GET", url, params=params)

            if response.status_code == 200:
                content = response.json().get("content", "")
                data = base64.b64decode(content)
                try:
                    return data.decode("utf-8")
                except UnicodeDecodeError:
                    safe_print("✗ Il file sembra binario; usare read_file_raw o download_file per ottenere i bytes")
                    return None
            elif response.status_code == 404:
                return None
            else:
                safe_print(f"Errore nella lettura: {response.status_code}")
                return None
        except Exception as e:
            safe_print(f"Errore: {e}")
            return None

    def read_file_raw(self, file_path: str) -> Optional[bytes]:
        """
        Legge il contenuto base64 e ritorna i bytes grezzi (utile per file binari).
        """
        try:
            url = f"{self.base_url}/contents/{file_path}"
            params = {"ref": self.branch}
            response = self._request("GET", url, params=params)
            if response.status_code == 200:
                content = response.json().get("content", "")
                return base64.b64decode(content)
            elif response.status_code == 404:
                return None
            else:
                safe_print(f"Errore nella lettura raw: {response.status_code}")
                return None
        except Exception as e:
            safe_print(f"Errore: {e}")
            return None

    def create_or_update_file(self, file_path: str, content: str, 
                             commit_message: str, author_name: str = "GitHub File Manager",
                             author_email: str = "bot@github.com") -> bool:
        """
        Crea o aggiorna un file nel repository.
        content: string (testo) OR base64-encoded string preceded by "base64:" if caller already encoded
        Per compatibilità col comportamento precedente, se 'content' è testo verrà codificato in UTF-8.
        """
        try:
            url = f"{self.base_url}/contents/{file_path}"
            sha = self.get_file_sha(file_path)

            # Detect if provided content is already base64
            if content.startswith("base64:"):
                encoded_content = content[len("base64:"):]
            else:
                # Content may be binary - caller should provide binary content as base64:... via helper
                # Here assume text and encode utf-8
                encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

            payload = {
                "message": commit_message,
                "content": encoded_content,
                "branch": self.branch,
                "committer": {
                    "name": author_name,
                    "email": author_email
                }
            }

            if sha:
                payload["sha"] = sha
                action = "aggiornato"
            else:
                action = "creato"

            response = self._request("PUT", url, json=payload)
            if response.status_code in [201, 200]:
                safe_print(f"✓ File {action} con successo: {file_path}")
                try:
                    safe_print(f"  SHA: {response.json()['content']['sha'][:7]}")
                except Exception:
                    pass
                return True
            else:
                safe_print(f"✗ Errore nell'operazione ({response.status_code}): {file_path}")
                safe_print(response.text)
                return False
        except requests.RequestException as e:
            safe_print(f"✗ Errore di connessione: {e}")
            return False
        except Exception as e:
            safe_print(f"✗ Errore: {e}")
            return False

    def delete_file(self, file_path: str, commit_message: str) -> bool:
        """
        Elimina un file dal repository.
        """
        try:
            sha = self.get_file_sha(file_path)
            if not sha:
                safe_print(f"✗ File non trovato: {file_path}")
                return False

            url = f"{self.base_url}/contents/{file_path}"
            payload = {
                "message": commit_message,
                "sha": sha,
                "branch": self.branch
            }

            response = self._request("DELETE", url, json=payload)

            if response.status_code == 200:
                safe_print(f"✓ File eliminato con successo: {file_path}")
                return True
            else:
                safe_print(f"✗ Errore nell'eliminazione ({response.status_code})")
                safe_print(response.text)
                return False
        except Exception as e:
            safe_print(f"✗ Errore: {e}")
            return False

    def batch_upload(self, files: List[Dict[str, str]], commit_message: str, dry_run: bool = False) -> int:
        """
        Carica più file in una singola operazione (ma sotto il cofano esegue più PUT).
        files: lista di dict con 'path' e 'content'. Per file binari usare content="base64:<B64STRING>"
        dry_run: se True non invia richieste PUT ma conta e mostra cosa sarebbe fatto.
        """
        success_count = 0
        for file_data in files:
            if "path" not in file_data or "content" not in file_data:
                safe_print("✗ Errore: file_data deve contenere 'path' e 'content'")
                continue

            if dry_run:
                safe_print(f"[DRY-RUN] Sarebbe caricato: {file_data['path']}")
                success_count += 1
            else:
                if self.create_or_update_file(
                    file_data["path"],
                    file_data["content"],
                    f"{commit_message} - {file_data['path']}"
                ):
                    success_count += 1

        safe_print(f"\nRiepilogo: {success_count}/{len(files)} file caricati con successo")
        return success_count

    def upload_from_directory(self, local_dir: str, repo_path: str = "",
                             commit_message: str = "Upload files from directory",
                             dry_run: bool = False) -> int:
        """
        Carica tutti i file di una directory locale.
        Supporta file binari (vengono letti in rb e inviati come base64 prefissato con 'base64:').
        """
        success_count = 0
        local_path = Path(local_dir)

        if not local_path.is_dir():
            safe_print(f"✗ Directory non trovata: {local_dir}")
            return 0

        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_path)
                if repo_path:
                    github_path = f"{repo_path}/{relative_path}".replace("\\", "/")
                else:
                    github_path = str(relative_path).replace("\\", "/")

                try:
                    # Proviamo ad aprire in binario e decidere se è testo o binario
                    with open(file_path, "rb") as f:
                        data = f.read()

                    if self._is_binary_bytes(data):
                        # invia base64 e segnala al create_or_update_file che è già base64
                        encoded = base64.b64encode(data).decode("utf-8")
                        content_field = f"base64:{encoded}"
                    else:
                        # testo
                        content_field = data.decode("utf-8")

                    if dry_run:
                        safe_print(f"[DRY-RUN] Sarebbe caricato: {github_path}")
                        success_count += 1
                    else:
                        if self.create_or_update_file(
                            github_path,
                            content_field,
                            f"{commit_message}: {relative_path}"
                        ):
                            success_count += 1
                except (UnicodeDecodeError, IOError) as e:
                    safe_print(f"✗ Errore nella lettura di {file_path}: {e}")

        safe_print(f"\nRiepilogo: {success_count} file caricati con successo da {local_dir}")
        return success_count

    # ---------- New methods ----------
    def download_file(self, file_path: str, local_path: str) -> bool:
        """
        Scarica un file dal repository e lo salva su disco (mantiene binario <-> testo).
        """
        try:
            data = self.read_file_raw(file_path)
            if data is None:
                safe_print("✗ File non trovato o errore")
                return False
            p = Path(local_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)
            safe_print(f"✓ File scaricato in: {local_path}")
            return True
        except Exception as e:
            safe_print(f"✗ Errore nel download: {e}")
            return False

    def list_directory(self, dir_path: str = "") -> Optional[List[Dict[str, Any]]]:
        """
        Lista il contenuto di una directory remota nel repository.
        Se dir_path è vuoto, lista la root.
        Ritorna la lista di entries (ogni entry è il JSON restituito da GitHub) oppure None in caso di errore.
        """
        try:
            if dir_path:
                url = f"{self.base_url}/contents/{dir_path}"
            else:
                url = f"{self.base_url}/contents"
            params = {"ref": self.branch}
            response = self._request("GET", url, params=params)
            if response.status_code == 200:
                items = response.json()
                if isinstance(items, list):
                    for item in items:
                        safe_print(f"{item.get('type', '?')}\t{item.get('path')}")
                    return items
                else:
                    # potrebbe essere un singolo file
                    safe_print(f"File: {items.get('path')}")
                    return [items]
            elif response.status_code == 404:
                safe_print("✗ Directory non trovata")
                return None
            else:
                safe_print(f"✗ Errore ({response.status_code})")
                safe_print(response.text)
                return None
        except Exception as e:
            safe_print(f"✗ Errore nella list_directory: {e}")
            return None

    def get_default_branch(self) -> Optional[str]:
        """
        Recupera il default branch del repository.
        """
        try:
            url = f"{self.base_url}"
            response = self._request("GET", url)
            if response.status_code == 200:
                return response.json().get("default_branch")
            else:
                return None
        except Exception:
            return None

    def create_branch(self, branch_name: str, base_ref: Optional[str] = None) -> bool:
        """
        Crea un nuovo branch (ref) a partire da base_ref (nome del branch) o dal default branch se base_ref è None.
        Richiede permessi push al repository.
        """
        try:
            if base_ref is None:
                base_ref = self.get_default_branch() or self.branch
            # Ottieni la sha del base_ref
            ref_url = f"{self.base_url}/git/refs/heads/{base_ref}"
            resp = self._request("GET", ref_url)
            if resp.status_code != 200:
                safe_print(f"✗ Impossibile ottenere ref base '{base_ref}': {resp.status_code}")
                return False
            base_sha = resp.json()["object"]["sha"]
            payload = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
            create_url = f"{self.base_url}/git/refs"
            create_resp = self._request("POST", create_url, json=payload)
            if create_resp.status_code in (201,):
                safe_print(f"✓ Branch creato: {branch_name} (da {base_ref})")
                return True
            else:
                safe_print(f"✗ Errore nella creazione del branch ({create_resp.status_code})")
                safe_print(create_resp.text)
                return False
        except Exception as e:
            safe_print(f"✗ Errore: {e}")
            return False

    def get_commits_for_path(self, file_path: str, per_page: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        Recupera la cronologia dei commit che hanno toccato file_path.
        """
        try:
            url = f"{self.base_url}/commits"
            params = {"path": file_path, "per_page": per_page}
            response = self._request("GET", url, params=params)
            if response.status_code == 200:
                commits = response.json()
                for c in commits:
                    sha = c.get("sha", "")[:7]
                    date = c.get("commit", {}).get("author", {}).get("date", "")
                    msg = c.get("commit", {}).get("message", "").splitlines()[0]
                    author = c.get("commit", {}).get("author", {}).get("name", "")
                    safe_print(f"{sha}\t{date}\t{author}\t{msg}")
                return commits
            else:
                safe_print(f"✗ Errore nel recupero dei commit ({response.status_code})")
                return None
        except Exception as e:
            safe_print(f"✗ Errore: {e}")
            return None


# ---------- Config helpers ----------
def load_config(config_file: str = "github_config.json") -> Optional[Dict]:
    """
    Carica la configurazione da un file JSON.
    """
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            safe_print(f"Errore nel caricamento della configurazione: {e}")
            return None
    return None


def save_config(config: Dict, config_file: str = "github_config.json") -> bool:
    """
    Salva la configurazione in un file JSON.
    """
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        safe_print(f"✓ Configurazione salvata in {config_file}")
        return True
    except Exception as e:
        safe_print(f"✗ Errore nel salvataggio della configurazione: {e}")
        return False


# ---------- Interactive menu (esteso) ----------
def interactive_menu(manager: GitHubFileManager):
    """Menu interattivo per operazioni sui file (esteso)"""

    while True:
        safe_print("\n" + "="*60)
        safe_print("GitHub File Manager - Menu Principale (esteso)")
        safe_print("="*60)
        safe_print("1. Creare/Aggiornare un singolo file")
        safe_print("2. Eliminare un file")
        safe_print("3. Leggere un file dal repository (testo)")
        safe_print("4. Scaricare file sul disco locale")
        safe_print("5. Caricare file da una directory locale")
        safe_print("6. Caricare più file (batch)")
        safe_print("7. Cambiare ramo (branch)")
        safe_print("8. Creare un nuovo branch dal branch base/default")
        safe_print("9. Lista contenuto di una directory remota")
        safe_print("10. Mostra cronologia commit per un file")
        safe_print("11. Toggle logging su file / Imposta file log")
        safe_print("12. Esci")
        safe_print("="*60)

        choice = input("Scegli un'opzione (1-12): ").strip()

        if choice == "1":
            file_path = input("Percorso del file nel repository: ").strip()
            if not file_path:
                safe_print("✗ Percorso non valido")
                continue

            source = input("Carica da file locale? (s/n): ").strip().lower()
            if source == "s":
                local_file = input("Percorso del file locale: ").strip()
                try:
                    with open(local_file, "rb") as f:
                        data = f.read()
                    if manager._is_binary_bytes(data):
                        content = "base64:" + base64.b64encode(data).decode("utf-8")
                    else:
                        content = data.decode("utf-8")
                except Exception as e:
                    safe_print(f"✗ Errore: {e}")
                    continue
            else:
                safe_print("Inserisci il contenuto (digita 'END' su una nuova riga per terminare):")
                lines = []
                while True:
                    line = input()
                    if line == "END":
                        break
                    lines.append(line)
                content = "\n".join(lines)

            message = input("Messaggio di commit: ").strip() or "Update file"
            manager.create_or_update_file(file_path, content, message)

        elif choice == "2":
            file_path = input("Percorso del file da eliminare: ").strip()
            message = input("Messaggio di commit: ").strip() or "Delete file"
            manager.delete_file(file_path, message)

        elif choice == "3":
            file_path = input("Percorso del file da leggere: ").strip()
            content = manager.read_file(file_path)
            if content is not None:
                safe_print("\n" + "="*60)
                safe_print(f"Contenuto di {file_path}:")
                safe_print("="*60)
                safe_print(content)
                safe_print("="*60)
            else:
                safe_print("✗ File non trovato o file binario (usa l'opzione 4 per scaricarlo)")

        elif choice == "4":
            file_path = input("Percorso del file nel repository: ").strip()
            local_path = input("Percorso locale dove salvare: ").strip()
            manager.download_file(file_path, local_path)

        elif choice == "5":
            local_dir = input("Percorso della directory locale: ").strip()
            repo_path = input("Percorso base nel repository (opzionale): ").strip()
            message = input("Messaggio di commit: ").strip() or "Upload directory"
            dry = input("Modalità dry-run (non esegue l'upload)? (s/n): ").strip().lower() == "s"
            manager.upload_from_directory(local_dir, repo_path, message, dry_run=dry)

        elif choice == "6":
            try:
                num_files = int(input("Quanti file vuoi caricare? "))
            except ValueError:
                safe_print("✗ Numero non valido")
                continue
            files = []
            for i in range(num_files):
                safe_print(f"\nFile {i+1}:")
                path = input("  Percorso nel repository: ").strip()
                local_file = input("  Percorso del file locale (o premi Invio per input manuale): ").strip()

                if local_file:
                    try:
                        with open(local_file, "rb") as f:
                            data = f.read()
                        if manager._is_binary_bytes(data):
                            content = "base64:" + base64.b64encode(data).decode("utf-8")
                        else:
                            content = data.decode("utf-8")
                    except Exception as e:
                        safe_print(f"  ✗ Errore: {e}")
                        continue
                else:
                    safe_print("  Inserisci il contenuto (digita 'END' su una nuova riga per terminare):")
                    lines = []
                    while True:
                        line = input("    ")
                        if line == "END":
                            break
                        lines.append(line)
                    content = "\n".join(lines)

                files.append({"path": path, "content": content})

            message = input("Messaggio di commit: ").strip() or "Batch upload"
            dry = input("Modalità dry-run (non esegue l'upload)? (s/n): ").strip().lower() == "s"
            manager.batch_upload(files, message, dry_run=dry)

        elif choice == "7":
            new_branch = input("Nome del nuovo ramo: ").strip()
            if new_branch:
                manager.branch = new_branch
                safe_print(f"✓ Ramo cambiato a: {new_branch}")

        elif choice == "8":
            branch_name = input("Nome del nuovo branch da creare: ").strip()
            base = input("Base branch (lascia vuoto per default branch): ").strip() or None
            if branch_name:
                manager.create_branch(branch_name, base_ref=base)

        elif choice == "9":
            dir_path = input("Percorso della directory remota (lascia vuoto per root): ").strip()
            manager.list_directory(dir_path)

        elif choice == "10":
            file_path = input("Percorso del file: ").strip()
            manager.get_commits_for_path(file_path)

        elif choice == "11":
            lf = input("Percorso file di log (lascia vuoto per disabilitare): ").strip()
            manager.log_file = lf if lf else None
            safe_print(f"✓ Logging impostato a: {manager.log_file}")

        elif choice == "12":
            safe_print("Arrivederci!")
            break

        else:
            safe_print("✗ Opzione non valida")


# ---------- CLI ----------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GitHub File Manager (esteso)")
    sub = p.add_subparsers(dest="cmd", required=False)

    # Common arguments for many subcommands
    def add_common_args(sp):
        sp.add_argument("--owner", help="Proprietario del repository")
        sp.add_argument("--repo", help="Nome del repository")
        sp.add_argument("--token", help="GitHub Personal Access Token")
        sp.add_argument("--branch", help="Branch (override)", default=None)
        sp.add_argument("--config", help="File di configurazione JSON (default: github_config.json)", default="github_config.json")
        sp.add_argument("--log-file", help="File dove scrivere log", default=None)

    # interactive
    interactive = sub.add_parser("interactive", help="Avvia menu interattivo")
    add_common_args(interactive)

    # create/update single
    cu = sub.add_parser("put", help="Create or update single file")
    add_common_args(cu)
    cu.add_argument("path", help="Percorso nel repo")
    cu.add_argument("--local", help="File locale da caricare")
    cu.add_argument("--message", help="Commit message", default="Update file")
    cu.add_argument("--author-name", help="Commit author name", default="GitHub File Manager")
    cu.add_argument("--author-email", help="Commit author email", default="bot@github.com")

    # delete
    d = sub.add_parser("delete", help="Delete file")
    add_common_args(d)
    d.add_argument("path", help="Percorso nel repo")
    d.add_argument("--message", help="Commit message", default="Delete file")

    # read
    r = sub.add_parser("read", help="Read file (text)")
    add_common_args(r)
    r.add_argument("path", help="Percorso nel repo")

    # download
    dl = sub.add_parser("download", help="Download file to local")
    add_common_args(dl)
    dl.add_argument("path", help="Percorso nel repo")
    dl.add_argument("local", help="Percorso locale dove salvare")

    # upload-dir
    ud = sub.add_parser("upload-dir", help="Upload directory")
    add_common_args(ud)
    ud.add_argument("local_dir", help="Directory locale")
    ud.add_argument("--repo-path", help="Base path nel repo", default="")
    ud.add_argument("--message", help="Commit message", default="Upload directory")
    ud.add_argument("--dry-run", help="Dry run (non esegue upload)", action="store_true")

    # batch
    b = sub.add_parser("batch", help="Batch upload described in JSON file")
    add_common_args(b)
    b.add_argument("json_file", help="JSON file with list of {path, content} entries")
    b.add_argument("--message", help="Commit message", default="Batch upload")
    b.add_argument("--dry-run", help="Dry run", action="store_true")

    # list-dir
    ld = sub.add_parser("list-dir", help="List directory on repo")
    add_common_args(ld)
    ld.add_argument("--path", help="Directory path (empty -> root)", default="")

    # create-branch
    cb = sub.add_parser("create-branch", help="Create a new branch")
    add_common_args(cb)
    cb.add_argument("branch_name", help="Nome nuovo branch")
    cb.add_argument("--base", help="Base branch (default: repo default branch)", default=None)

    # commits
    cm = sub.add_parser("commits", help="Show commits touching a path")
    add_common_args(cm)
    cm.add_argument("path", help="Percorso file")
    cm.add_argument("--per-page", help="Numero di commit", type=int, default=30)

    return p


def merge_config_with_args(args: argparse.Namespace) -> Dict:
    config = {}
    file_conf = {}
    if getattr(args, "config", None):
        file_conf = load_config(args.config) or {}
    # precedence: CLI args > config file > env vars > defaults
    config["owner"] = getattr(args, "owner", None) or file_conf.get("owner") or os.getenv("GITHUB_OWNER")
    config["repo"] = getattr(args, "repo", None) or file_conf.get("repo") or os.getenv("GITHUB_REPO")
    config["token"] = getattr(args, "token", None) or file_conf.get("token") or os.getenv("GITHUB_TOKEN")
    br = getattr(args, "branch", None) or file_conf.get("branch") or os.getenv("GITHUB_BRANCH")
    config["branch"] = br or "main"
    config["log_file"] = getattr(args, "log_file", None) or file_conf.get("log_file")
    return config


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    # If no args or interactive explicitly, run interactive mode
    if not vars(args) or args.cmd is None or args.cmd == "interactive":
        # Try to load config
        cfg = load_config("github_config.json") or {}
        owner = cfg.get("owner") or input("Proprietario del repository: ").strip()
        repo = cfg.get("repo") or input("Nome del repository: ").strip()
        token = cfg.get("token") or os.getenv("GITHUB_TOKEN") or input("GitHub Personal Access Token: ").strip()
        branch = cfg.get("branch") or input("Ramo (default: main): ").strip() or "main"
        log_file = cfg.get("log_file")
        if not cfg:
            save = input("Salvare la configurazione per future sessioni? (s/n): ").strip().lower()
            if save == "s":
                save_config({"owner": owner, "repo": repo, "token": token, "branch": branch, "log_file": log_file})
        manager = GitHubFileManager(owner, repo, token, branch, log_file=log_file)
        safe_print(f"\n✓ Connesso a {owner}/{repo} su ramo '{branch}'")
        interactive_menu(manager)
        return

    # Non-interactive flows
    config = merge_config_with_args(args)
    missing = [k for k in ("owner", "repo", "token") if not config.get(k)]
    if missing:
        safe_print(f"✗ Parametri mancanti: {missing}. Fornisci --owner/--repo/--token o un file config.")
        sys.exit(1)

    manager = GitHubFileManager(config["owner"], config["repo"], config["token"], branch=config.get("branch", "main"), log_file=config.get("log_file"))

    cmd = args.cmd
    if cmd == "put":
        if args.local:
            with open(args.local, "rb") as f:
                data = f.read()
            if manager._is_binary_bytes(data):
                content = "base64:" + base64.b64encode(data).decode("utf-8")
            else:
                content = data.decode("utf-8")
        else:
            safe_print("Inserisci il contenuto (CTRL-D per terminare):")
            content = sys.stdin.read()
        manager.create_or_update_file(args.path, content, args.message, author_name=args.author_name, author_email=args.author_email)

    elif cmd == "delete":
        manager.delete_file(args.path, args.message)

    elif cmd == "read":
        out = manager.read_file(args.path)
        if out is None:
            safe_print("✗ Nulla da mostrare (file binario o non trovato). Usa 'download' per salvare i bytes.")
        else:
            safe_print(out)

    elif cmd == "download":
        manager.download_file(args.path, args.local)

    elif cmd == "upload-dir":
        manager.upload_from_directory(args.local_dir, args.repo_path, args.message, dry_run=args.dry_run)

    elif cmd == "batch":
        try:
            with open(args.json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                safe_print("✗ Il JSON deve essere una lista di oggetti con 'path' e 'content'.")
                sys.exit(1)
            manager.batch_upload(data, args.message, dry_run=args.dry_run)
        except Exception as e:
            safe_print(f"✗ Errore nel leggere il JSON: {e}")
            sys.exit(1)

    elif cmd == "list-dir":
        manager.list_directory(args.path or "")

    elif cmd == "create-branch":
        manager.create_branch(args.branch_name, base_ref=args.base)

    elif cmd == "commits":
        manager.get_commits_for_path(args.path, per_page=args.per_page)

    else:
        safe_print("Comando non riconosciuto")
        parser.print_help()


if __name__ == "__main__":
    main()
