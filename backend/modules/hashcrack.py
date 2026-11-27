#!/usr/bin/python3
# -*- encoding: utf-8 -*-
"""Backend hash-cracking worker.

Mirrors the other backend tool workers (see ``steghide.py``): a long-lived loop
that claims queued jobs from Mongo, runs the tools, and writes results back.
Unlike the image workers it is driven by the ``hash_jobs`` collection rather than
the upload folder, so its artifacts never collide with the steganography scan dir.

For each job it:
  * detects the hash type of every line with regex/length heuristics (no subprocess),
  * runs John the Ripper and Hashcat **in parallel** per hash-type group,
  * streams tool output into ``hash_jobs.progress.log`` for live SSE display,
  * records one result per input line, and
  * caches cracked results in ``hash_cache`` keyed by ``sha256(hash_value)``.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.append('../')

DELAY_CHECK = 5           # seconds between polls for queued jobs
HASHJOBS_DIR = os.environ.get("HASHJOBS_DIR", "/app/hashjobs")
DEFAULT_WORDLIST = os.environ.get(
    "DEFAULT_WORDLIST", "/usr/share/wordlists/rockyou.txt")
# Core `john` (1.8) cannot handle raw-* formats, so the image builds John Jumbo
# and points JOHN_BIN at it. HASHCAT_BIN can be disabled where the binary is broken.
JOHN_BIN = os.environ.get("JOHN_BIN", "john")
HASHCAT_BIN = os.environ.get("HASHCAT_BIN", "hashcat")

# label -> (hashcat mode, john format)
HASHCAT_MODES = {
    'MD5': '0', 'SHA1': '100', 'SHA224': '1300', 'SHA256': '1400',
    'SHA384': '10800', 'SHA512': '1700', 'NTLM': '1000', 'LM': '3000',
    'bcrypt': '3200', 'sha512crypt': '1800', 'sha256crypt': '7400',
    'md5crypt': '500', 'MySQL323': '200', 'MySQL4+': '300', 'WPA': '22000',
}
JOHN_FORMATS = {
    'MD5': 'raw-md5', 'SHA1': 'raw-sha1', 'SHA224': 'raw-sha224',
    'SHA256': 'raw-sha256', 'SHA384': 'raw-sha384', 'SHA512': 'raw-sha512',
    'NTLM': 'nt', 'LM': 'lm', 'bcrypt': 'bcrypt', 'sha512crypt': 'sha512crypt',
    'sha256crypt': 'sha256crypt', 'md5crypt': 'md5crypt', 'MySQL323': 'mysql',
    'MySQL4+': 'mysql-sha1', 'WPA': 'wpapsk',
}

# UI rule name -> hashcat rule file. John falls back to its default --rules set.
HASHCAT_RULES = {
    'best64': '/usr/share/hashcat/rules/best64.rule',
    'toggles': '/usr/share/hashcat/rules/toggles1.rule',
    'dive': '/usr/share/hashcat/rules/dive.rule',
}

_HEX = re.compile(r'^[0-9a-fA-F]+$')
_BCRYPT = re.compile(r'^\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}$')
_MYSQL4 = re.compile(r'^\*[0-9A-Fa-f]{40}$')


def detect_hash_type(h):
    """Return (label, hashcat_mode, john_format) using heuristics only.

    ``hashid`` is only consulted as a last-resort fallback when it is installed
    and the heuristics cannot classify the input.
    """
    h = (h or '').strip()
    by_len = {32: 'MD5', 40: 'SHA1', 56: 'SHA224',
              64: 'SHA256', 96: 'SHA384', 128: 'SHA512'}

    label = None
    if _BCRYPT.match(h):
        label = 'bcrypt'
    elif h.startswith('$6$'):
        label = 'sha512crypt'
    elif h.startswith('$5$'):
        label = 'sha256crypt'
    elif h.startswith('$1$'):
        label = 'md5crypt'
    elif _MYSQL4.match(h):
        label = 'MySQL4+'
    elif h.count('*') >= 3 and _HEX.match(h.split('*')[0] or ''):
        label = 'WPA'            # PMKID-style line: <pmkid>*<mac>*<mac>*<essid>
    elif _HEX.match(h):
        if len(h) == 16:
            label = 'MySQL323'
        else:
            label = by_len.get(len(h))

    if label is None:
        label = _hashid_fallback(h)

    if label is None:
        label = 'MD5'            # safe default

    return label, HASHCAT_MODES.get(label, '0'), JOHN_FORMATS.get(label, 'raw-md5')


def _hashid_fallback(h):
    """Best-effort hashid lookup; returns a label we support or None."""
    try:
        out = subprocess.check_output(
            ['hashid', '-m', h], stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return None
    for line in out.splitlines():
        for label in HASHCAT_MODES:
            if label.lower() in line.lower():
                return label
    return None


def map_show(known_hashes, show_text, john=False):
    """Map a tool's --show output back to the known input hashes.

    Lines are ``<hash>:<plaintext>...``; we match by hash prefix so a ``:`` in
    the plaintext does not break parsing. John appends extra ``:`` fields, so for
    John we keep only the first field after the hash.
    """
    found = {}
    lines = (show_text or '').splitlines()
    for h in known_hashes:
        for line in lines:
            prefix = h + ':'
            if line.startswith(prefix):
                rest = line[len(prefix):]
                found[h] = rest.split(':')[0] if john else rest
                break
    return found


def push_log(job_id, line):
    from mongo import db_hash_jobs
    db_hash_jobs.update_one(
        {"_id": job_id},
        {"$push": {"progress.log": {"t": time.time(), "line": line}}})


def run_and_stream(cmd_list, label, job_id):
    """Run a command, streaming each output line into the job log; return output."""
    push_log(job_id, f"$ {' '.join(cmd_list)}")
    try:
        proc = subprocess.Popen(
            cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
    except FileNotFoundError:
        push_log(job_id, f"[{label}] not installed on this host")
        return ""
    out_lines = []
    try:
        for line in proc.stdout:
            line = line.rstrip('\n')
            if line:
                out_lines.append(line)
                push_log(job_id, f"[{label}] {line}")
    finally:
        proc.wait()
    return '\n'.join(out_lines)


def _capture(cmd_list):
    try:
        return subprocess.check_output(
            cmd_list, stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return ""


def parse_pot(known_hashes, pot_path):
    """Map known hashes to plaintext from a John pot file.

    Pot lines are ``<ciphertext>:<plaintext>`` where the ciphertext embeds the
    hash (e.g. ``$dynamic_0$<md5hex>:pw`` for raw-md5, or the full hash itself
    for bcrypt/sha512crypt). The hash is matched as a substring so format tags do
    not matter; splitting on the first ``:`` preserves ``:`` in the plaintext.
    """
    found = {}
    try:
        with open(pot_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return found
    low = [(ln.split(":", 1)) for ln in lines if ":" in ln]
    for h in known_hashes:
        hl = h.lower()
        for cipher, plain in low:
            if hl in cipher.lower():
                found[h] = plain
                break
    return found


def run_john(hashes, group_file, john_fmt, wordlist, rule, job_id):
    if not JOHN_BIN:
        return {}
    pot_path = group_file + ".pot"
    cmd = [JOHN_BIN, f'--format={john_fmt}', f'--wordlist={wordlist}',
           f'--pot={pot_path}']
    if rule:
        cmd.append('--rules')
    cmd.append(group_file)
    run_and_stream(cmd, 'john', job_id)
    return parse_pot(hashes, pot_path)


def run_hashcat(hashes, group_file, mode, wordlist, rule, job_id):
    if not HASHCAT_BIN:
        return {}
    cmd = [HASHCAT_BIN, '-m', mode, '-a', '0', '--force', group_file, wordlist]
    rule_file = HASHCAT_RULES.get(rule)
    if rule and rule_file and os.path.exists(rule_file):
        cmd += ['-r', rule_file]
    elif rule:
        push_log(job_id, f"[hashcat] rule '{rule}' unavailable, ignoring")
    run_and_stream(cmd, 'hashcat', job_id)
    show = _capture([HASHCAT_BIN, '-m', mode, group_file, '--show'])
    return map_show(hashes, show, john=False)


def process_job(job):
    from mongo import db_hash_jobs, db_hash_cache
    job_id = job["_id"]
    entries = job.get("hashes", [])
    rule = (job.get("rules") or "").strip().lower() or None
    wordlist = job.get("wordlist_path") or DEFAULT_WORDLIST

    if not os.path.exists(wordlist):
        db_hash_jobs.update_one({"_id": job_id}, {"$set": {
            "status": "error",
            "error": f"Wordlist not found: {wordlist}",
            "finished": time.time()}})
        return

    push_log(job_id, f"Wordlist: {wordlist}")
    # Classify each line and group by (john_format, hashcat_mode).
    groups = {}
    for e in entries:
        label, mode, jfmt = detect_hash_type(e["line"])
        e["hash_type"], e["hashcat_mode"], e["john_format"] = label, mode, jfmt
        groups.setdefault((jfmt, mode), []).append(e["line"])
    db_hash_jobs.update_one({"_id": job_id}, {"$set": {"hashes": entries}})

    cracked = {}   # hash -> (plaintext, via)
    work_dir = tempfile.mkdtemp(prefix="hc_")
    try:
        for (jfmt, mode), lines in groups.items():
            push_log(job_id, f"Group {jfmt}/{mode}: {len(lines)} hash(es)")
            group_file = os.path.join(work_dir, f"{jfmt}_{mode}.txt")
            with open(group_file, "w") as f:
                f.write("\n".join(lines) + "\n")
            # John and Hashcat run concurrently on the same group.
            with ThreadPoolExecutor(max_workers=2) as ex:
                fj = ex.submit(run_john, lines, group_file, jfmt,
                               wordlist, rule, job_id)
                fh = ex.submit(run_hashcat, lines, group_file, mode,
                               wordlist, rule, job_id)
                john_found = fj.result()
                hashcat_found = fh.result()
            for h in lines:
                if h in hashcat_found:
                    cracked[h] = (hashcat_found[h], "hashcat")
                elif h in john_found:
                    cracked[h] = (john_found[h], "john")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    # Record per-line results + populate cache.
    now = time.time()
    for e in entries:
        h = e["line"]
        if h in cracked:
            plain, via = cracked[h]
            e["cracked"], e["via"] = plain, via
            db_hash_cache.update_one(
                {"_id": hashlib.sha256(h.encode()).hexdigest()},
                {"$set": {"hash": h, "hash_type": e.get("hash_type"),
                          "plaintext": plain, "via": via, "ts": now}},
                upsert=True)
        else:
            e["cracked"], e["via"] = None, None

    db_hash_jobs.update_one({"_id": job_id}, {"$set": {
        "hashes": entries, "status": "done", "finished": now}})
    push_log(job_id, "Done.")


def claim_next():
    """Atomically claim one queued job, or return None."""
    from mongo import db_hash_jobs
    return db_hash_jobs.find_one_and_update(
        {"status": "queued"},
        {"$set": {"status": "running", "started": time.time()}})


def report_health():
    """Publish wordlist availability so the web UI can warn accurately."""
    from mongo import db_hash_meta
    db_hash_meta.update_one(
        {"_id": "health"},
        {"$set": {"wordlist": DEFAULT_WORDLIST,
                  "wordlist_present": os.path.exists(DEFAULT_WORDLIST),
                  "ts": time.time()}},
        upsert=True)


def main():
    os.makedirs(HASHJOBS_DIR, exist_ok=True)
    try:
        report_health()
    except Exception as e:          # noqa: BLE001
        print(f"hashcrack health error: {e}", flush=True)
    while True:
        try:
            job = claim_next()
            if job is not None:
                process_job(job)
                continue
        except Exception as e:      # noqa: BLE001 - keep the worker alive
            print(f"hashcrack error: {e}", flush=True)
        time.sleep(DELAY_CHECK)


if __name__ == "__main__":
    main()
