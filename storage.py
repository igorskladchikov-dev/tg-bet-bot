# -*- coding: utf-8 -*-
"""Simple JSON storage for users and bets."""
import json
from datetime import datetime
from pathlib import Path

INITIAL_BALANCE = 10_000  # rubles per user
DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_FILE = DATA_DIR / "users.json"
BETS_FILE = DATA_DIR / "bets.json"
SETTLE_LOG_FILE = DATA_DIR / "settlements.log"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path, default):
    _ensure_dir()
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(path, data):
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(user_id: int, username: str = "") -> dict:
    """Get or create user with initial balance."""
    users = _load_json(USERS_FILE, {})
    key = str(user_id)
    if key not in users:
        users[key] = {
            "user_id": user_id,
            "username": username or "",
            "balance": INITIAL_BALANCE,
        }
        _save_json(USERS_FILE, users)
    return users[key]


def update_balance(user_id: int, delta: int) -> int:
    """Update balance by delta (positive or negative). Returns new balance."""
    users = _load_json(USERS_FILE, {})
    key = str(user_id)
    if key not in users:
        return 0
    users[key]["balance"] = max(0, users[key]["balance"] + delta)
    _save_json(USERS_FILE, users)
    return users[key]["balance"]


def get_balance(user_id: int) -> int:
    u = get_user(user_id)
    return u["balance"]


def create_bet(user_id: int, description: str, rate: float, sum_rub: int) -> dict | None:
    """Create bet. Deducts sum from balance. Returns bet dict or None if not enough balance."""
    balance = get_balance(user_id)
    if sum_rub <= 0 or sum_rub > balance:
        return None
    bets = _load_json(BETS_FILE, [])
    bet_id = max((b.get("id", 0) for b in bets), default=0) + 1
    bet = {
        "id": bet_id,
        "user_id": user_id,
        "description": description,
        "rate": rate,
        "sum": sum_rub,
        "status": "active",  # active | won | lost
    }
    bets.append(bet)
    _save_json(BETS_FILE, bets)
    update_balance(user_id, -sum_rub)
    return bet


def get_user_bets(user_id: int, status: str | None = None) -> list:
    """Get bets for user, optionally filter by status (active, won, lost)."""
    bets = _load_json(BETS_FILE, [])
    out = [b for b in bets if b["user_id"] == user_id]
    if status:
        out = [b for b in out if b.get("status") == status]
    return sorted(out, key=lambda x: x["id"], reverse=True)


def get_bet(bet_id: int) -> dict | None:
    bets = _load_json(BETS_FILE, [])
    for b in bets:
        if b.get("id") == bet_id:
            return b
    return None


def settle_bet(
    bet_id: int,
    won: bool,
    settled_by_user_id: int | None = None,
    settled_by_username: str = "",
) -> bool:
    """Mark bet as won or lost, update balance, log who closed it. Returns True if updated."""
    bets = _load_json(BETS_FILE, [])
    for i, b in enumerate(bets):
        if b.get("id") == bet_id and b.get("status") == "active":
            b["status"] = "won" if won else "lost"
            b["settled_at"] = datetime.now().isoformat()
            b["settled_by_user_id"] = settled_by_user_id
            b["settled_by_username"] = settled_by_username or ""
            user_id = b["user_id"]
            if won:
                payout = int(b["sum"] * b["rate"])
                update_balance(user_id, payout)
            _save_json(BETS_FILE, bets)
            # Лог: кто и как закрыл ставку
            _ensure_dir()
            outcome = "won" if won else "lost"
            who = f"@{settled_by_username}" if settled_by_username else str(settled_by_user_id or "?")
            with open(SETTLE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | bet_id={bet_id} | "
                    f"user_id={settled_by_user_id} | {who} | outcome={outcome}\n"
                )
            return True
    return False


def get_all_users_balances() -> list:
    """List all users and balances (for admin/leaderboard)."""
    users = _load_json(USERS_FILE, {})
    return [
        {"user_id": int(k), "username": v.get("username", ""), "balance": v["balance"]}
        for k, v in users.items()
    ]


def reset_all_balances_to_initial() -> int:
    """Set every user's balance to INITIAL_BALANCE. Returns number of users reset."""
    users = _load_json(USERS_FILE, {})
    for key in users:
        users[key]["balance"] = INITIAL_BALANCE
    _save_json(USERS_FILE, users)
    return len(users)
