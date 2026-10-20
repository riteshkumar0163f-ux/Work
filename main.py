#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLORY2 main CLI
  1 = Solo (1 account)
  2 = Duo  (2 accounts)
  3 = Squad (4 accounts)
Manual accounts only → accounts.json
Real MajorLogin (engine) → show nickname/level → guild silent leave/join → BR TCP match
"""
from __future__ import annotations

import os
import sys
import json
import time
import asyncio
import warnings
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

ACCOUNTS_JSON = BASE / "accounts.json"
CONFIG_JSON = BASE / "glory_config.json"

# ─── lightweight crypto/clan for pre-engine guild switch ───
try:
    import requests
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
except ImportError:
    print("pip install -r requirements.txt")
    sys.exit(1)

import urllib3
urllib3.disable_warnings()

AES_KEY = b"Yg&tc%DEuh6%Zc^8"
AES_IV = b"6oyZDr22E3ychjM%"
OB = "OB55"
UA = "Dalvik/2.1.0 (Linux; U; Android 9)"
REGION_HOST = {
    "IND": "https://client.ind.freefiremobile.com",
    "ID": "https://clientbp.ggpolarbear.com",
    "SG": "https://clientbp.ggpolarbear.com",
    "TH": "https://clientbp.ggpolarbear.com",
    "VN": "https://clientbp.ggpolarbear.com",
    "BR": "https://client.us.freefiremobile.com",
    "BD": "https://clientbp.ggwhitehawk.com",
    "PK": "https://clientbp.ggblueshark.com",
    "ME": "https://clientbp.ggblueshark.com",
}


def cprint(msg: str, kind: str = "i"):
    tag = {"i": "[i]", "+": "[+]", "!": "[!]", "-": "[-]", "1": "[1]"}.get(kind, "[i]")
    print(f">> {tag} {msg}", flush=True)


def ask(prompt: str, default: str = "") -> str:
    try:
        v = input(prompt).strip()
    except EOFError:
        v = ""
    return v if v else default


def load_accounts() -> List[dict]:
    if not ACCOUNTS_JSON.exists():
        return []
    try:
        raw = json.loads(ACCOUNTS_JSON.read_text(encoding="utf-8") or "[]")
    except Exception as e:
        cprint(f"accounts.json error: {e}", "-")
        return []
    out = []
    if not isinstance(raw, list):
        return []
    for item in raw:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("uid") or "").strip()
        pw = str(item.get("password") or item.get("pass") or "").strip()
        if not uid or not pw or uid.upper().startswith("YOUR_"):
            continue
        out.append({"uid": uid, "password": pw})
    return out


def save_selected_accounts(rows: List[dict]):
    """Write the accounts the engine will actually run."""
    ACCOUNTS_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def aes_encrypt(data: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(data, 16))


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            break
    return bytes(out)


def field_varint(num: int, v: int) -> bytes:
    return varint((num << 3) | 0) + varint(int(v))


def leave_clan_silent(jwt: str, region: str) -> bool:
    base = REGION_HOST.get((region or "IND").upper(), REGION_HOST["IND"])
    headers = {
        "User-Agent": UA,
        "Authorization": f"Bearer {jwt}" if not str(jwt).startswith("Bearer") else jwt,
        "Content-Type": "application/octet-stream",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": OB,
        "Host": base.replace("https://", "").split("/")[0],
    }
    for path in ("/LeaveClan", "/ClanLeave", "/RequestLeaveClan"):
        for body in (aes_encrypt(b""), aes_encrypt(field_varint(1, 1))):
            try:
                r = requests.post(f"{base}{path}", headers=headers, data=body, timeout=12, verify=False)
                if r.status_code == 200:
                    return True
            except Exception:
                continue
    return False


def join_clan_silent(jwt: str, clan_id: int, region: str) -> bool:
    try:
        import ReqCLan_pb2 as pb
        msg = pb.MyMessage()
        msg.field_1 = int(clan_id)
        body = aes_encrypt(msg.SerializeToString())
    except Exception:
        body = aes_encrypt(field_varint(1, int(clan_id)))
    base = REGION_HOST.get((region or "IND").upper(), REGION_HOST["IND"])
    headers = {
        "User-Agent": UA,
        "Authorization": f"Bearer {jwt}" if not str(jwt).startswith("Bearer") else jwt,
        "Content-Type": "application/octet-stream",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": OB,
        "Host": base.replace("https://", "").split("/")[0],
    }
    try:
        r = requests.post(f"{base}/RequestJoinClan", headers=headers, data=body, timeout=15, verify=False)
        return r.status_code == 200
    except Exception:
        return False


async def real_login_and_profile(uid: str, password: str) -> Optional[dict]:
    """Use engine MajorLogin path — real TCP-ready session data."""
    # Ensure local folder is on path (Termux extract / nested folders)
    here = str(BASE)
    if here not in sys.path:
        sys.path.insert(0, here)
    os.chdir(BASE)
    # Guarantee ReqCLan alias file exists
    req_a = BASE / "ReqCLan_pb2.py"
    req_b = BASE / "reqClan_pb2.py"
    try:
        if req_b.exists() and not req_a.exists():
            req_a.write_bytes(req_b.read_bytes())
        elif req_a.exists() and not req_b.exists():
            req_b.write_bytes(req_a.read_bytes())
    except Exception:
        pass
    try:
        import engine as eng
    except Exception as e:
        cprint(f"engine import failed: {e}", "-")
        cprint(f"cwd={os.getcwd()} files={sorted(x.name for x in BASE.glob('*.py'))[:15]}", "!")
        return None
    try:
        ad = await eng.process_account_uid_pass(uid, password)
        return ad
    except Exception as e:
        cprint(f"login exception: {e}", "-")
        return None


def print_profile(ad: dict):
    acc_id = ad.get("account_id")
    nick = ad.get("nickname") or "—"
    region = ad.get("region") or "—"
    level = ad.get("level") or "—"
    exp = ad.get("exp") or 0
    likes = ad.get("likes") or 0
    print("╭━━━ REAL ACCOUNT ━━━╮", flush=True)
    print(f"│ Name     : {nick}", flush=True)
    print(f"│ Account  : {acc_id}", flush=True)
    print(f"│ GuestUID : {ad.get('auth_uid')}", flush=True)
    print(f"│ Region   : {region}", flush=True)
    print(f"│ Level    : {level}", flush=True)
    print(f"│ EXP      : {exp}", flush=True)
    print(f"│ Likes    : {likes}", flush=True)
    print(f"│ Server   : {ad.get('server_url') or '—'}", flush=True)
    print(f"│ TCP Func : {ad.get('functional_addrs') or '—'}", flush=True)
    print("╰━━━━━━━━━━━━━━━━━━━━╯", flush=True)


async def guild_switch_for_session(ad: dict, clan_id: int):
    token = ad.get("token")
    region = ad.get("region") or "IND"
    if not token:
        return
    # silent
    try:
        leave_clan_silent(token, region)
    except Exception:
        pass
    await asyncio.sleep(0.3)
    try:
        join_clan_silent(token, clan_id, region)
    except Exception:
        pass


async def run_flow():
    print("\n≫≫ FYT SQUAD BOT 《  (BR ONLY — REAL TCP)\n", flush=True)

    accounts = load_accounts()
    if not accounts:
        cprint("accounts.json empty. Add accounts manually:", "-")
        print('[{"uid":"8313770107","password":"..."}]')
        return

    cprint(f"accounts.json loaded: {len(accounts)} account(s)", "+")

    print(">> [i] 1) Solo   — 1 bot plays solo")
    print(">> [i] 2) Duo    — 2 bots play together")
    print(">> [i] 3) Squad  — 4 bots play squad\n")
    opt = ask("Option chuno (1/2/3): ", "")
    if opt not in ("1", "2", "3"):
        cprint("Invalid option. Use 1, 2 or 3.", "-")
        return

    need = {"1": 1, "2": 2, "3": 4}[opt]
    mode_name = {"1": "SOLO", "2": "DUO", "3": "SQUAD"}[opt]

    if len(accounts) < need:
        cprint(
            f"Mode {mode_name} needs {need} account(s), but accounts.json has only {len(accounts)}. STOP.",
            "-",
        )
        return

    selected = accounts[:need]
    cprint(f"[MODE] {mode_name} | need={need} | selected={len(selected)}", "+")
    cprint("Mode: BATTLE ROYALE ONLY (real TCP matchmaking)", "i")

    # Real login each selected account — show real profile (no fake)
    sessions: List[dict] = []
    for i, acc in enumerate(selected, 1):
        uid, pw = acc["uid"], acc["password"]
        cprint(f"[LOGIN] ({i}/{len(selected)}) UID {uid}...", "i")
        ad = await real_login_and_profile(uid, pw)
        if not ad:
            cprint(f"Login FAILED for {uid} — fix password or network. STOP.", "-")
            return
        cprint(f"Login OK → {ad.get('nickname')} | Lvl {ad.get('level')}", "+")
        print_profile(ad)
        sessions.append(ad)

    # Guild after real TCP login data available
    clan_raw = ask("\nGuild / Clan UID (khali = skip guild): ", "")
    clan_id = int(clan_raw) if clan_raw.isdigit() else None
    if clan_id:
        cprint(f"[CLAN] {clan_id} — silent leave (if any) + join...", "i")
        for ad in sessions:
            await guild_switch_for_session(ad, clan_id)
        cprint("[CLAN] done (silent)", "+")
    else:
        cprint("[CLAN] skipped", "i")

    # Persist config for engine TEAM_SIZE
    cfg = {
        "team_size": need,
        "team_mode": need > 1,
        "mode_name": mode_name,
        "clan_id": clan_id,
        "br_only": True,
    }
    CONFIG_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    # Only selected accounts for engine
    save_selected_accounts(selected)
    cprint("Config saved. Starting REAL BR TCP workers...", "+")

    # Start engine main loop (full TCP / matchmaking)
    import engine as eng
    # engine.main already loads accounts.json and starts workers
    await eng.main()


def self_test() -> bool:
    ok = True
    cprint("SELF-TEST", "i")
    need_files = [
        "main.py", "engine.py", "app.py", "dashboard_server.py", "accounts.json",
        "data_pb2.py", "encode_id_clan_pb2.py", "reqClan_pb2.py", "StartMatch_pb2.py",
        "thunderFF_pb2.py", "message_ids.py", "FYTTF_pb2.py", "FYTTteam_pb2.py",
    ]
    for n in need_files:
        if not (BASE / n).exists():
            cprint(f"MISSING {n}", "-")
            ok = False
        else:
            cprint(f"OK {n}", "+")
    accs = load_accounts()
    cprint(f"accounts loaded: {len(accs)}", "+")
    # mode validation logic
    for opt, need in (("1", 1), ("2", 2), ("3", 4)):
        if len(accs) < need:
            cprint(f"mode {opt} would STOP (need {need}, have {len(accs)})", "i")
        else:
            cprint(f"mode {opt} OK with current accounts", "+")
    try:
        import data_pb2, encode_id_clan_pb2, reqClan_pb2, StartMatch_pb2, thunderFF_pb2  # noqa
        cprint("protobuf OK", "+")
    except Exception as e:
        cprint(f"proto fail {e}", "-")
        ok = False
    cprint("SELF-TEST " + ("PASS" if ok else "FAIL"), "1" if ok else "-")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "test"):
        sys.exit(0 if self_test() else 1)
    try:
        asyncio.run(run_flow())
    except KeyboardInterrupt:
        cprint("stopped", "!")
