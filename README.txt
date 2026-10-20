GLORY2 — BR ONLY — Solo / Duo / Squad

1. Edit accounts.json (manual only):
[
  {"uid":"8313770107","password":"YOUR_PASS"},
  {"uid":"...","password":"..."}
]

2. pip install -r requirements.txt
3. python main.py --test
4. python main.py

Modes:
  1 Solo  = 1 account required
  2 Duo   = 2 accounts required
  3 Squad = 4 accounts required
If not enough accounts → auto STOP.

Flow:
  login (real) → show name/level/TCP addrs → Guild UID → silent leave+join → BR TCP matchmaking
