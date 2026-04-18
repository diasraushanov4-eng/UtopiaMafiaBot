import logging
import os
import random
import sqlite3
from dataclasses import dataclass
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("utopia_mafia_bot")

DB_PATH = os.getenv("DB_PATH", "bot.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ----- Role engine metadata -----
PHASE1_MVP_ROLES = [
    "Don",
    "Mafia",
    "Qotil",
    "Komissar",
    "Doktor",
    "Serjant",
    "Janob",
    "Tinch aholi",
    "Kezuvchi",
    "Advokat",
    "Daydi",
    "Konchi",
]
PHASE2_ADVANCED_ROLES = [
    "Labarant",
    "Zombi",
    "Qaroqchi",
    "Minior",
    "Jurnalist",
    "Kimyogar",
    "Bo‘ri",
    "G‘azabkor",
    "Yollanma qotil",
    "Sotqin",
    "Qorbobo",
    "Koldun",
]

ROLE_SPECS = {
    "Don": {"team": "mafia", "goal": "Kill civilians", "ui": "kill"},
    "Mafia": {"team": "mafia", "goal": "Support Don", "ui": "kill"},
    "Qotil": {"team": "solo", "goal": "Last alive", "ui": "kill"},
    "Komissar": {"team": "civil", "goal": "Find mafia", "ui": "check_or_shoot"},
    "Doktor": {"team": "civil", "goal": "Save players", "ui": "heal"},
    "Serjant": {"team": "civil", "goal": "Inherit Komissar", "ui": "passive"},
    "Janob": {"team": "civil", "goal": "4 votes day", "ui": "passive"},
    "Tinch aholi": {"team": "civil", "goal": "Vote mafia out", "ui": "passive"},
    "Daydi": {"team": "civil", "goal": "Witness", "ui": "watch"},
    "Kezuvchi": {"team": "civil", "goal": "Block", "ui": "block"},
    "Advokat": {"team": "mafia", "goal": "Hide mafia identity", "ui": "protect"},
    "Suitsid": {"team": "solo", "goal": "Win if executed", "ui": "passive"},
    "Omadli": {"team": "civil", "goal": "Chance survive", "ui": "passive"},
    "Bo‘ri": {"team": "wild", "goal": "Transform", "ui": "passive"},
    "Yollanma qotil": {"team": "mafia", "goal": "Hidden kill", "ui": "kill"},
    "G‘azabkor": {"team": "solo", "goal": "Mark targets", "ui": "mark"},
    "Jurnalist": {"team": "civil", "goal": "Visitor logs", "ui": "watch"},
    "Admiral": {"team": "civil", "goal": "Immortal condition", "ui": "passive"},
    "Kimyogar": {"team": "neutral", "goal": "Heal or kill", "ui": "heal_or_poison"},
    "Rais": {"team": "civil", "goal": "Daily economy", "ui": "money"},
    "Minior": {"team": "civil", "goal": "Place mine", "ui": "trap"},
    "Robin Gud": {"team": "civil", "goal": "Steal/transfer", "ui": "steal"},
    "Ayg‘oqchi": {"team": "mafia", "goal": "Spy", "ui": "watch"},
    "Konchi": {"team": "solo", "goal": "Mine result", "ui": "mine_pick"},
    "Fotoparatchi": {"team": "civil", "goal": "Take photo", "ui": "watch"},
    "Qaroqchi": {"team": "neutral", "goal": "Rob", "ui": "steal"},
    "Zombi": {"team": "neutral", "goal": "Infect", "ui": "infect"},
    "Labarant": {"team": "neutral", "goal": "Poison", "ui": "poison"},
    "Hamshira": {"team": "civil", "goal": "Inherit doctor", "ui": "passive"},
    "Koldun": {"team": "neutral", "goal": "Protect/kill by side", "ui": "select"},
    "Qorbobo": {"team": "neutral", "goal": "Gift", "ui": "gift"},
    "Joker": {"team": "solo", "goal": "Suspicious play", "ui": "passive"},
    "Sotqin": {"team": "neutral", "goal": "Betray", "ui": "passive"},
    "Aferist": {"team": "neutral", "goal": "Scam", "ui": "steal"},
}

DEFAULT_ROLE_POOL = PHASE1_MVP_ROLES.copy()

NIGHT_ROLES = {r for r, spec in ROLE_SPECS.items() if spec["ui"] != "passive"}

# Item engine (auto-trigger + priority)
ITEM_PRIORITY = [
    "himoya",  # protection
    "qotildan_himoya",  # killer protection
    "doridan_himoya",  # anti poison
    "sirpanishdan_himoya",  # mine protection
    "osishdan_himoya",  # anti hang
]


@dataclass
class Player:
    user_id: int
    role: str
    money: int
    diamonds: int


class Repo:
    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT NOT NULL DEFAULT 'player',
                money INTEGER NOT NULL DEFAULT 0,
                diamonds INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(user_id, item)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS partner_groups (
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, chat_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                chat_id INTEGER PRIMARY KEY,
                creator_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                day_no INTEGER NOT NULL DEFAULT 0,
                players TEXT NOT NULL DEFAULT ''
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS game_roles (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role_name TEXT NOT NULL,
                alive INTEGER NOT NULL DEFAULT 1,
                last_night_action INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(chat_id, user_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS game_actions (
                chat_id INTEGER NOT NULL,
                night_no INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                action_text TEXT NOT NULL,
                PRIMARY KEY(chat_id, night_no, actor_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS game_votes (
                chat_id INTEGER NOT NULL,
                day_no INTEGER NOT NULL,
                voter_id INTEGER NOT NULL,
                target_id INTEGER,
                PRIMARY KEY(chat_id, day_no, voter_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS casino_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                bet INTEGER NOT NULL,
                payout INTEGER NOT NULL,
                result TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_casino_stats (
                user_id INTEGER PRIMARY KEY,
                win_streak INTEGER NOT NULL DEFAULT 0,
                lose_streak INTEGER NOT NULL DEFAULT 0,
                total_wager INTEGER NOT NULL DEFAULT 0,
                total_payout INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()
        self._seed_settings()

    def _seed_settings(self) -> None:
        defaults = {
            # Casino settings
            "casino.dice_mult": "3.0",
            "casino.blackjack_mult": "2.0",
            "casino.roulette_color_mult": "2.0",
            "casino.roulette_zero_mult": "14.0",
            "casino.mines_base_mult": "1.35",
            "casino.target_rtp.mines": "0.92",
            "casino.target_rtp.blackjack": "0.96",
            "casino.target_rtp.roulette": "0.94",
            "casino.target_rtp.telegram": "0.90",
            # Game settings
            "game.min_players": "4",
            "game.max_players": "12",
            "game.turn_timer_sec": "30",
            "game.auto_start": "0",
            # Anti farm
            "antifarm.reward_mult": "1.0",
            "antifarm.transfer_fee": "0.00",
            "antifarm.casino_rtp_mult": "1.0",
            # Panel editable text
            "text.start": "Welcome to UtopiaMafiaBot",
            "text.news_channel": "@news_channel",
            "text.official_channel": "@official_channel",
            "text.buy_contact": "@payment_admin",
            "text.inactive.mafia": "Mafia shahardan qochib ketdi",
            "text.inactive.doctor": "Doktor shaharni tark etdi",
            "text.kill.don": "{target} ni Don vahshiylarcha yo‘q qildi",
            "text.kill.mafia": "{target} ni Mafia yashirincha yo‘q qildi",
            "text.kill.komissar": "{target} Komissarning qiynoqlariga chiday olmadi",
            "text.kill.maniac": "{target} maniacning qurboni bo‘ldi",
        }
        for k, v in defaults.items():
            self.conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()

    def get_setting(self, key: str, fallback: str) -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else fallback

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def ensure_user(self, user_id: int, username: Optional[str] = None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO users(user_id, username, role, money, diamonds) VALUES (?, ?, 'player', 1000, 10)",
            (user_id, username),
        )
        self.conn.execute("UPDATE users SET username = COALESCE(?, username) WHERE user_id = ?", (username, user_id))
        if DEFAULT_OWNER_ID and user_id == DEFAULT_OWNER_ID:
            self.conn.execute("UPDATE users SET role='owner' WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_player(self, user_id: int) -> Optional[Player]:
        row = self.conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        return Player(row["user_id"], row["role"], row["money"], row["diamonds"])

    def set_role(self, user_id: int, role: str) -> None:
        self.conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        self.conn.commit()

    def transfer_money(self, from_id: int, to_id: int, amount: int, unlimited: bool = False) -> tuple[bool, str]:
        sender = self.get_player(from_id)
        receiver = self.get_player(to_id)
        if not sender or not receiver:
            return False, "Foydalanuvchi topilmadi"
        if amount <= 0:
            return False, "Miqdor musbat bo'lishi kerak"
        if not unlimited and sender.money < amount:
            return False, "Balans yetarli emas"
        if not unlimited:
            self.conn.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (amount, from_id))
        self.conn.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, to_id))
        self.conn.commit()
        return True, "OK"

    def transfer_diamonds(self, from_id: int, to_id: int, amount: int, unlimited: bool = False) -> tuple[bool, str]:
        sender = self.get_player(from_id)
        receiver = self.get_player(to_id)
        if not sender or not receiver:
            return False, "Foydalanuvchi topilmadi"
        if amount <= 0:
            return False, "Miqdor musbat bo'lishi kerak"
        if not unlimited and sender.diamonds < amount:
            return False, "Olmos yetarli emas"
        if not unlimited:
            self.conn.execute("UPDATE users SET diamonds = diamonds - ? WHERE user_id = ?", (amount, from_id))
        self.conn.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (amount, to_id))
        self.conn.commit()
        return True, "OK"

    def add_money(self, user_id: int, amount: int) -> None:
        self.conn.execute("UPDATE users SET money=money+? WHERE user_id=?", (amount, user_id))
        self.conn.commit()

    def add_diamonds(self, user_id: int, amount: int) -> None:
        self.conn.execute("UPDATE users SET diamonds=diamonds+? WHERE user_id=?", (amount, user_id))
        self.conn.commit()

    def add_item(self, user_id: int, item: str, amount: int, enabled: int = 1) -> None:
        self.conn.execute(
            "INSERT INTO inventory(user_id, item, count, enabled) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id,item) DO UPDATE SET count = count + excluded.count",
            (user_id, item, amount, enabled),
        )
        self.conn.commit()

    def remove_item(self, user_id: int, item: str, amount: int) -> tuple[bool, str]:
        row = self.conn.execute("SELECT count FROM inventory WHERE user_id=? AND item=?", (user_id, item)).fetchone()
        have = row["count"] if row else 0
        if have < amount:
            return False, "Inventarda yetarli item yo'q"
        self.conn.execute("UPDATE inventory SET count = count - ? WHERE user_id=? AND item=?", (amount, user_id, item))
        self.conn.commit()
        return True, "OK"

    def get_item(self, user_id: int, item: str):
        return self.conn.execute(
            "SELECT count, enabled FROM inventory WHERE user_id=? AND item=?", (user_id, item)
        ).fetchone()

    def set_item_toggle(self, user_id: int, item: str, enabled: int) -> None:
        self.conn.execute(
            "INSERT INTO inventory(user_id,item,count,enabled) VALUES (?, ?, 0, ?) "
            "ON CONFLICT(user_id,item) DO UPDATE SET enabled=excluded.enabled",
            (user_id, item, enabled),
        )
        self.conn.commit()

    def can_partner_control(self, user_id: int, chat_id: int) -> bool:
        row = self.conn.execute("SELECT 1 FROM partner_groups WHERE user_id=? AND chat_id=?", (user_id, chat_id)).fetchone()
        return bool(row)

    def add_partner_group(self, user_id: int, chat_id: int) -> None:
        self.conn.execute("INSERT OR IGNORE INTO partner_groups(user_id, chat_id) VALUES (?, ?)", (user_id, chat_id))
        self.conn.commit()

    def new_game(self, chat_id: int, creator_id: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO games(chat_id, creator_id, status, day_no, players) VALUES (?, ?, 'lobby', 0, '')",
            (chat_id, creator_id),
        )
        self.conn.execute("DELETE FROM game_roles WHERE chat_id=?", (chat_id,))
        self.conn.execute("DELETE FROM game_actions WHERE chat_id=?", (chat_id,))
        self.conn.execute("DELETE FROM game_votes WHERE chat_id=?", (chat_id,))
        self.conn.commit()

    def get_game(self, chat_id: int):
        return self.conn.execute("SELECT * FROM games WHERE chat_id=?", (chat_id,)).fetchone()

    def list_game_chats(self):
        return self.conn.execute("SELECT chat_id FROM games").fetchall()

    def set_game_status(self, chat_id: int, status: str) -> None:
        self.conn.execute("UPDATE games SET status=? WHERE chat_id=?", (status, chat_id))
        self.conn.commit()

    def inc_day(self, chat_id: int) -> int:
        self.conn.execute("UPDATE games SET day_no = day_no + 1 WHERE chat_id=?", (chat_id,))
        self.conn.commit()
        g = self.get_game(chat_id)
        return g["day_no"] if g else 0

    def set_game_players(self, chat_id: int, players_csv: str) -> None:
        self.conn.execute("UPDATE games SET players=? WHERE chat_id=?", (players_csv, chat_id))
        self.conn.commit()

    def delete_game(self, chat_id: int) -> None:
        self.conn.execute("DELETE FROM games WHERE chat_id=?", (chat_id,))
        self.conn.execute("DELETE FROM game_roles WHERE chat_id=?", (chat_id,))
        self.conn.execute("DELETE FROM game_actions WHERE chat_id=?", (chat_id,))
        self.conn.execute("DELETE FROM game_votes WHERE chat_id=?", (chat_id,))
        self.conn.commit()

    def set_game_role(self, chat_id: int, user_id: int, role_name: str) -> None:
        self.conn.execute(
            "INSERT INTO game_roles(chat_id, user_id, role_name, alive, last_night_action) VALUES (?, ?, ?, 1, 0) "
            "ON CONFLICT(chat_id,user_id) DO UPDATE SET role_name=excluded.role_name, alive=1",
            (chat_id, user_id, role_name),
        )
        self.conn.commit()

    def get_alive_roles(self, chat_id: int):
        return self.conn.execute(
            "SELECT * FROM game_roles WHERE chat_id=? AND alive=1 ORDER BY user_id", (chat_id,)
        ).fetchall()

    def get_user_role_in_chat(self, chat_id: int, user_id: int):
        return self.conn.execute("SELECT * FROM game_roles WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()

    def set_dead(self, chat_id: int, user_id: int) -> None:
        self.conn.execute("UPDATE game_roles SET alive=0 WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        self.conn.commit()

    def set_night_action(self, chat_id: int, night_no: int, actor_id: int, action_text: str) -> None:
        self.conn.execute(
            "INSERT INTO game_actions(chat_id, night_no, actor_id, action_text) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id,night_no,actor_id) DO UPDATE SET action_text=excluded.action_text",
            (chat_id, night_no, actor_id, action_text),
        )
        self.conn.execute(
            "UPDATE game_roles SET last_night_action=? WHERE chat_id=? AND user_id=?",
            (night_no, chat_id, actor_id),
        )
        self.conn.commit()

    def get_night_actions(self, chat_id: int, night_no: int):
        return self.conn.execute(
            "SELECT * FROM game_actions WHERE chat_id=? AND night_no=?", (chat_id, night_no)
        ).fetchall()

    def cast_vote(self, chat_id: int, day_no: int, voter_id: int, target_id: Optional[int]) -> None:
        self.conn.execute(
            "INSERT INTO game_votes(chat_id, day_no, voter_id, target_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id,day_no,voter_id) DO UPDATE SET target_id=excluded.target_id",
            (chat_id, day_no, voter_id, target_id),
        )
        self.conn.commit()

    def tally_votes(self, chat_id: int, day_no: int):
        return self.conn.execute(
            "SELECT target_id, COUNT(*) as c FROM game_votes WHERE chat_id=? AND day_no=? GROUP BY target_id ORDER BY c DESC",
            (chat_id, day_no),
        ).fetchall()

    def add_casino_history(self, user_id: int, game: str, bet: int, payout: int, result: str) -> None:
        self.conn.execute(
            "INSERT INTO casino_history(user_id, game, bet, payout, result) VALUES (?, ?, ?, ?, ?)",
            (user_id, game, bet, payout, result),
        )
        won = 1 if payout > 0 else 0
        self.conn.execute(
            "INSERT OR IGNORE INTO user_casino_stats(user_id, win_streak, lose_streak, total_wager, total_payout) VALUES (?, 0, 0, 0, 0)",
            (user_id,),
        )
        if won:
            self.conn.execute(
                "UPDATE user_casino_stats SET win_streak=win_streak+1, lose_streak=0, total_wager=total_wager+?, total_payout=total_payout+? WHERE user_id=?",
                (bet, payout, user_id),
            )
        else:
            self.conn.execute(
                "UPDATE user_casino_stats SET lose_streak=lose_streak+1, win_streak=0, total_wager=total_wager+?, total_payout=total_payout+? WHERE user_id=?",
                (bet, payout, user_id),
            )
        self.conn.commit()

    def casino_last(self, user_id: int, limit: int = 10):
        return self.conn.execute(
            "SELECT game, bet, payout, result, created_at FROM casino_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()

    def get_casino_stats(self, user_id: int):
        row = self.conn.execute(
            "SELECT win_streak, lose_streak, total_wager, total_payout FROM user_casino_stats WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if row:
            return row
        return {"win_streak": 0, "lose_streak": 0, "total_wager": 0, "total_payout": 0}


repo = Repo(DB_PATH)


def is_admin_or_owner(role: str) -> bool:
    return role in {"admin", "owner"}


def no_permission_text() -> str:
    return "❌ Sizda bu buyruqni ishlatish huquqi yo‘q (access denied)."


def parse_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_bet_limits(player: Player) -> tuple[int, int, str]:
    # Simple leveling based on balance
    if player.money >= 5000:
        return 100, 5000, "VIP"
    if player.money >= 1000:
        return 50, 1000, "Normal"
    return 10, 200, "Beginner"


def effective_rtp_multiplier(user_id: int) -> float:
    stats = repo.get_casino_stats(user_id)
    base = float(repo.get_setting("antifarm.casino_rtp_mult", "1.0"))
    # anti-abuse: win streak > 5 lowers RTP
    if stats["win_streak"] > 5:
        base *= 0.85
    return base


async def _ensure(update: Update) -> Player:
    user = update.effective_user
    repo.ensure_user(user.id, user.username)
    p = repo.get_player(user.id)
    return p


def apply_defense_pipeline(target_id: int, cause: str) -> tuple[bool, str]:
    """Returns (blocked, message)."""
    # priority 1: basic protection
    row = repo.get_item(target_id, "himoya")
    if row and row["enabled"] and row["count"] > 0:
        repo.remove_item(target_id, "himoya", 1)
        return True, "🛡 Hujum himoya bilan bloklandi"

    # priority 2: killer protection chance
    if cause in {"kill", "shoot"}:
        row = repo.get_item(target_id, "qotildan_himoya")
        if row and row["enabled"] and row["count"] > 0 and random.random() < 0.70:
            repo.remove_item(target_id, "qotildan_himoya", 1)
            return True, "⛑ Qotildan himoya ishga tushdi"

    # priority 3: anti-poison
    if cause == "poison":
        row = repo.get_item(target_id, "doridan_himoya")
        if row and row["enabled"] and row["count"] > 0:
            repo.remove_item(target_id, "doridan_himoya", 1)
            return True, "💊 Doridan himoya ishladi"

    # priority 4: mine protection
    if cause == "mine":
        row = repo.get_item(target_id, "sirpanishdan_himoya")
        if row and row["enabled"] and row["count"] > 0:
            repo.remove_item(target_id, "sirpanishdan_himoya", 1)
            return True, "🪤 Sirpanishdan himoya ishladi"

    return False, ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type == ChatType.PRIVATE:
        start_text = repo.get_setting("text.start", "Welcome")
        keyboard = [
            [InlineKeyboardButton("👤 Profile", callback_data="panel:profile"), InlineKeyboardButton("🛒 Shop", callback_data="panel:shop")],
            [InlineKeyboardButton("🎰 Casino", callback_data="panel:casino"), InlineKeyboardButton("📊 Stats", callback_data="panel:stats")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="panel:admin")],
            [InlineKeyboardButton("⚙️ Owner Panel", callback_data="panel:owner")],
        ]
        # visibility
        visible = [keyboard[0], keyboard[1]]
        if is_admin_or_owner(me.role):
            visible.append(keyboard[2])
        if me.role == "owner":
            visible.append(keyboard[3])

        await update.message.reply_text(
            f"{start_text}\n\nRole: {me.role}\nBalans: ${me.money} | 💎 {me.diamonds}",
            reply_markup=InlineKeyboardMarkup(visible),
        )
    else:
        await update.message.reply_text("Bot ishlayapti ✅. Private chatda /start bosing.")


# ----- economy handlers -----
async def money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Format: reply + /money <sum>")
        return
    amount = parse_int(context.args[0])
    if amount is None:
        await update.message.reply_text("Miqdor son bo‘lishi kerak")
        return
    to_user = update.message.reply_to_message.from_user
    repo.ensure_user(to_user.id, to_user.username)
    ok, msg = repo.transfer_money(me.user_id, to_user.id, amount, unlimited=is_admin_or_owner(me.role))
    await update.message.reply_text(f"✅ {amount}$ yuborildi" if ok else f"❌ {msg}")


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Format: reply + /send <sum>")
        return
    amount = parse_int(context.args[0])
    if amount is None:
        await update.message.reply_text("Miqdor son bo‘lishi kerak")
        return
    to_user = update.message.reply_to_message.from_user
    repo.ensure_user(to_user.id, to_user.username)
    ok, msg = repo.transfer_diamonds(me.user_id, to_user.id, amount, unlimited=is_admin_or_owner(me.role))
    await update.message.reply_text(f"✅ {amount}💎 yuborildi" if ok else f"❌ {msg}")


async def give(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if not update.message.reply_to_message or len(context.args) < 2:
        await update.message.reply_text("Format: reply + /give <item> <count>")
        return
    item = context.args[0].lower()
    amount = parse_int(context.args[1])
    if amount is None:
        await update.message.reply_text("Soni son bo‘lishi kerak")
        return
    target = update.message.reply_to_message.from_user
    repo.ensure_user(target.id, target.username)
    if not is_admin_or_owner(me.role):
        ok, msg = repo.remove_item(me.user_id, item, amount)
        if not ok:
            await update.message.reply_text(f"❌ {msg}")
            return
    repo.add_item(target.id, item, amount)
    await update.message.reply_text(f"✅ {item} x{amount} berildi")


async def unmoney(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role not in {"admin", "owner"}:
        await update.message.reply_text(no_permission_text())
        return
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Format: reply + /unmoney <sum>")
        return
    amount = parse_int(context.args[0])
    if amount is None:
        await update.message.reply_text("Miqdor son bo‘lishi kerak")
        return
    target = update.message.reply_to_message.from_user
    repo.ensure_user(target.id, target.username)
    ok, msg = repo.transfer_money(target.id, me.user_id, amount, unlimited=False)
    await update.message.reply_text(f"✅ {amount}$ ayirildi" if ok else f"❌ {msg}")


async def unsend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role not in {"admin", "owner"}:
        await update.message.reply_text(no_permission_text())
        return
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Format: reply + /unsend <sum>")
        return
    amount = parse_int(context.args[0])
    if amount is None:
        await update.message.reply_text("Miqdor son bo‘lishi kerak")
        return
    target = update.message.reply_to_message.from_user
    repo.ensure_user(target.id, target.username)
    ok, msg = repo.transfer_diamonds(target.id, me.user_id, amount, unlimited=False)
    await update.message.reply_text(f"✅ {amount}💎 ayirildi" if ok else f"❌ {msg}")


async def ungive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role not in {"admin", "owner"}:
        await update.message.reply_text(no_permission_text())
        return
    if not update.message.reply_to_message or len(context.args) < 2:
        await update.message.reply_text("Format: reply + /ungive <item> <count>")
        return
    item = context.args[0].lower()
    amount = parse_int(context.args[1])
    if amount is None:
        await update.message.reply_text("Soni son bo‘lishi kerak")
        return
    target = update.message.reply_to_message.from_user
    repo.ensure_user(target.id, target.username)
    ok, msg = repo.remove_item(target.id, item, amount)
    await update.message.reply_text(f"✅ {item} x{amount} ayirildi" if ok else f"❌ {msg}")


# ----- game handlers -----
async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("/newgame faqat groupda")
        return
    repo.new_game(chat.id, update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Qo‘shilish", callback_data=f"join:{chat.id}")],
        [InlineKeyboardButton("👥 O‘yinchilar", callback_data=f"players:{chat.id}")],
    ])
    await update.message.reply_text("🎮 Yangi o‘yin yaratildi!\nO‘yinchilar: 0/12", reply_markup=kb)


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("/startgame faqat groupda")
        return
    game = repo.get_game(chat.id)
    if not game:
        await update.message.reply_text("Avval /newgame")
        return

    member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    is_group_admin = member.status in {"administrator", "creator"}
    if update.effective_user.id != game["creator_id"] and not is_group_admin:
        await update.message.reply_text("Faqat creator yoki group admin boshlaydi")
        return

    players = [int(x) for x in game["players"].split(",") if x]
    min_players = int(repo.get_setting("game.min_players", "4"))
    if len(players) < min_players:
        await update.message.reply_text(f"Kamida {min_players} o‘yinchi kerak")
        return

    random.shuffle(players)
    roles = DEFAULT_ROLE_POOL[: len(players)]
    if len(roles) < len(players):
        roles += ["Tinch aholi"] * (len(players) - len(roles))
    random.shuffle(roles)
    for uid, role in zip(players, roles):
        repo.set_game_role(chat.id, uid, role)

    repo.set_game_status(chat.id, "night")
    night_no = repo.inc_day(chat.id)
    await update.message.reply_text(f"🌙 Night {night_no} boshlandi. Private chatda /myrole <chat_id>.")


async def nextphase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("/nextphase faqat groupda")
        return

    game = repo.get_game(chat.id)
    if not game:
        await update.message.reply_text("Faol o‘yin yo‘q")
        return

    member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    is_group_admin = member.status in {"administrator", "creator"}
    if me.role not in {"admin", "owner"} and update.effective_user.id != game["creator_id"] and not is_group_admin:
        await update.message.reply_text(no_permission_text())
        return

    status = game["status"]
    if status == "night":
        night_no = game["day_no"]
        actions = repo.get_night_actions(chat.id, night_no)
        lines = [f"☀️ Tong otdi (Day {night_no})"]

        # inactivity text
        for r in repo.get_alive_roles(chat.id):
            if r["role_name"] == "Mafia" and r["last_night_action"] < night_no:
                lines.append("• " + repo.get_setting("text.inactive.mafia", ""))
            if r["role_name"] == "Doktor" and r["last_night_action"] < night_no:
                lines.append("• " + repo.get_setting("text.inactive.doctor", ""))

        # Priority system:
        # 1) BLOCK 2) ROLE MODIFY 3) CHECK 4) TRAP/PASSIVE 5) KILL 6) DEFENSE 7) STATUS 8) HEAL 9) RANDOM(MINER)
        blocked_actors: set[int] = set()
        hidden_ids: set[int] = set()
        heals: set[int] = set()
        pending_kills: list[tuple[int, str]] = []
        pending_poison: list[int] = []

        # 1) block
        for a in actions:
            if a["action_text"].startswith("block:"):
                target = parse_int(a["action_text"].split(":", 1)[1])
                if target is not None:
                    blocked_actors.add(target)

        # 2) role modify (advokat/document style)
        for a in actions:
            if a["actor_id"] in blocked_actors:
                continue
            if a["action_text"].startswith("protect:"):
                target = parse_int(a["action_text"].split(":", 1)[1])
                if target is not None:
                    hidden_ids.add(target)

        # 3) check
        for a in actions:
            if a["actor_id"] in blocked_actors:
                continue
            if a["action_text"].startswith("check:"):
                target = parse_int(a["action_text"].split(":", 1)[1])
                if target is None:
                    continue
                t_role = repo.get_user_role_in_chat(chat.id, target)
                result = "Civilian" if target in hidden_ids else (t_role["role_name"] if t_role else "Unknown")
                lines.append(f"🔍 Check result for {a['actor_id']}: User({target}) => {result}")

        # 4) trap/passive reserved

        # 5) kill and 7) poison enqueue (if actor not blocked)
        for a in actions:
            if a["actor_id"] in blocked_actors:
                continue
            act = a["action_text"]
            if act.startswith("kill:"):
                target = parse_int(act.split(":", 1)[1])
                if target is not None:
                    actor = repo.get_user_role_in_chat(chat.id, a["actor_id"])
                    rk = "text.kill.mafia"
                    if actor and actor["role_name"] == "Don":
                        rk = "text.kill.don"
                    elif actor and actor["role_name"] == "Komissar":
                        rk = "text.kill.komissar"
                    elif actor and actor["role_name"] == "Qotil":
                        rk = "text.kill.maniac"
                    pending_kills.append((target, rk))
            elif act.startswith("poison:"):
                target = parse_int(act.split(":", 1)[1])
                if target is not None:
                    pending_poison.append(target)
            elif act.startswith("heal:"):
                target = parse_int(act.split(":", 1)[1])
                if target is not None:
                    heals.add(target)

        # 6) defense items + 8) heal late-resolution
        died: set[int] = set()
        for target, rk in pending_kills:
            blocked, msg = apply_defense_pipeline(target, "kill")
            if blocked:
                lines.append(msg)
                continue
            if target in heals:
                lines.append(f"💉 Doctor kech davoladi: User({target}) tirik qoldi")
                continue
            died.add(target)
            lines.append("💀 " + repo.get_setting(rk, "{target} o‘ldirildi").format(target=f"User({target})"))

        for target in pending_poison:
            blocked, msg = apply_defense_pipeline(target, "poison")
            if blocked:
                lines.append(msg)
                continue
            if target in heals:
                lines.append(f"💉 Poison heal bilan qaytarildi: User({target})")
                continue
            died.add(target)
            lines.append(f"☠️ User({target}) zahardan o‘ldi")

        for uid in died:
            repo.set_dead(chat.id, uid)

        if not died and not pending_kills and not pending_poison:
            lines.append("🕊 Bu tun hech kim o‘lmadi")

        repo.set_game_status(chat.id, "day")
        await update.message.reply_text("\n".join(lines) + "\n\n/vote reply yoki replysiz skip")
        return

    if status == "day":
        day_no = game["day_no"]
        tally = repo.tally_votes(chat.id, day_no)
        if tally:
            top = tally[0]
            if top["target_id"] is not None:
                target = int(top["target_id"])
                blocked, msg = apply_defense_pipeline(target, "hang")
                if blocked:
                    await update.message.reply_text("⚖️ Osish bekor: " + msg)
                else:
                    # suitsid instant win condition
                    tr = repo.get_user_role_in_chat(chat.id, target)
                    if tr and tr["role_name"] == "Suitsid":
                        repo.delete_game(chat.id)
                        await update.message.reply_text("💀 Suitsid osildi va darhol yutdi!")
                        return
                    repo.set_dead(chat.id, target)
                    await update.message.reply_text(f"⚖️ Sud natijasi: User({target}) chiqarildi")
            else:
                await update.message.reply_text("⏭ Ovoz natijasi: skip")
        repo.set_game_status(chat.id, "court")
        return

    if status == "court":
        alive = repo.get_alive_roles(chat.id)
        mafia_like = sum(1 for x in alive if x["role_name"] in {"Don", "Mafia", "Advokat", "Yollanma qotil"})
        civil_like = len(alive) - mafia_like
        if mafia_like == 0:
            repo.delete_game(chat.id)
            for p in alive:
                repo.add_money(p["user_id"], 20)
            await update.message.reply_text("🎉 Tinch aholi yutdi (+20$)")
            return
        if mafia_like >= civil_like:
            repo.delete_game(chat.id)
            for p in alive:
                repo.add_money(p["user_id"], 20)
            await update.message.reply_text("🎉 Mafia tarafi yutdi (+20$)")
            return
        repo.set_game_status(chat.id, "night")
        nxt = repo.inc_day(chat.id)
        await update.message.reply_text(f"🌙 Keyingi tun boshlandi (Night {nxt})")
        return


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("/vote faqat groupda")
        return
    game = repo.get_game(chat.id)
    if not game or game["status"] != "day":
        await update.message.reply_text("Vote yopiq")
        return

    target_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else None
    # Janob: 4 votes
    self_role = repo.get_user_role_in_chat(chat.id, update.effective_user.id)
    repeat = 4 if self_role and self_role["role_name"] == "Janob" else 1
    for _ in range(repeat):
        repo.cast_vote(chat.id, game["day_no"], update.effective_user.id, target_id)
    await update.message.reply_text("🗳 Ovoz qabul qilindi")


async def myrole(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("/myrole private")
        return
    if not context.args:
        await update.message.reply_text("Format: /myrole <group_chat_id>")
        return
    chat_id = parse_int(context.args[0])
    if chat_id is None:
        await update.message.reply_text("chat_id son bo‘lishi kerak")
        return
    gr = repo.get_user_role_in_chat(chat_id, me.user_id)
    if not gr:
        await update.message.reply_text("Rol topilmadi")
        return
    await update.message.reply_text(
        f"🎭 Role: {gr['role_name']}\nTeam: {ROLE_SPECS.get(gr['role_name'], {}).get('team', '-')}")


async def action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("/action private")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Format: /action <chat_id> <kill:uid|check:uid|heal:uid|poison:uid|skip>")
        return
    chat_id = parse_int(context.args[0])
    if chat_id is None:
        await update.message.reply_text("chat_id son bo‘lishi kerak")
        return
    action_text = context.args[1]

    game = repo.get_game(chat_id)
    if not game or game["status"] != "night":
        await update.message.reply_text("Hozir night emas")
        return
    gr = repo.get_user_role_in_chat(chat_id, me.user_id)
    if not gr or not gr["alive"]:
        await update.message.reply_text("Siz tirik emassiz")
        return
    if gr["role_name"] not in NIGHT_ROLES:
        await update.message.reply_text("Bu rolda night action yo‘q")
        return

    repo.set_night_action(chat_id, game["day_no"], me.user_id, action_text)
    await update.message.reply_text("✅ Action qabul qilindi")


async def nightui(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Build button-based gameplay UI for role actions."""
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("/nightui private")
        return
    if not context.args:
        await update.message.reply_text("Format: /nightui <chat_id>")
        return

    chat_id = parse_int(context.args[0])
    if chat_id is None:
        await update.message.reply_text("chat_id son bo‘lishi kerak")
        return
    game = repo.get_game(chat_id)
    if not game or game["status"] != "night":
        await update.message.reply_text("Night bosqichi emas")
        return
    role = repo.get_user_role_in_chat(chat_id, me.user_id)
    if not role:
        await update.message.reply_text("Rol topilmadi")
        return

    role_name = role["role_name"]
    ui_kind = ROLE_SPECS.get(role_name, {}).get("ui", "passive")
    players = [r for r in repo.get_alive_roles(chat_id) if r["user_id"] != me.user_id]

    # step1 for complex roles
    if ui_kind == "check_or_shoot":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Tekshirish", callback_data=f"ract:mode:{chat_id}:check")],
            [InlineKeyboardButton("🔫 Otish", callback_data=f"ract:mode:{chat_id}:kill")],
            [InlineKeyboardButton("⏭ Skip", callback_data=f"ract:mode:{chat_id}:skip")],
        ])
        await update.message.reply_text("👮 Siz — Komissar\nTanlang:", reply_markup=kb)
        return
    if ui_kind == "heal_or_poison":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💊 Davolash", callback_data=f"ract:mode:{chat_id}:heal")],
            [InlineKeyboardButton("☠️ O‘ldirish", callback_data=f"ract:mode:{chat_id}:poison")],
            [InlineKeyboardButton("⏭ Skip", callback_data=f"ract:mode:{chat_id}:skip")],
        ])
        await update.message.reply_text("⚗️ Siz — Kimyogar\nTanlang:", reply_markup=kb)
        return
    if ui_kind == "mine_pick":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟫 Kon 1", callback_data=f"ract:mine:{chat_id}:1")],
            [InlineKeyboardButton("🟫 Kon 2", callback_data=f"ract:mine:{chat_id}:2")],
            [InlineKeyboardButton("🟫 Kon 3", callback_data=f"ract:mine:{chat_id}:3")],
        ])
        await update.message.reply_text("⛏ Siz — Konchi\nKon tanlang:", reply_markup=kb)
        return
    if ui_kind == "passive":
        await update.message.reply_text("Bu role passive. Night action yo‘q.")
        return

    mode_map = {
        "kill": "kill",
        "heal": "heal",
        "watch": "watch",
        "block": "block",
        "protect": "protect",
        "mark": "mark",
        "poison": "poison",
        "trap": "trap",
        "steal": "steal",
        "infect": "infect",
        "gift": "gift",
        "select": "select",
        "money": "money",
    }
    mode = mode_map.get(ui_kind, "skip")
    rows = [[InlineKeyboardButton(f"👤 {p['user_id']}", callback_data=f"ract:pick:{chat_id}:{mode}:{p['user_id']}")] for p in players[:12]]
    rows.append([InlineKeyboardButton("⏭ O‘tkazib yuborish", callback_data=f"ract:pick:{chat_id}:skip:0")])
    await update.message.reply_text(
        f"🎭 Role: {role_name}\nKerakli targetni tanlang:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("join:") or query.data.startswith("players:"):
        action, chat_id_str = query.data.split(":", 1)
        chat_id = int(chat_id_str)
        game = repo.get_game(chat_id)
        if not game:
            await query.edit_message_text("Lobby topilmadi")
            return
        players = [p for p in game["players"].split(",") if p]
        if action == "join":
            if str(query.from_user.id) not in players and len(players) < int(repo.get_setting("game.max_players", "12")):
                players.append(str(query.from_user.id))
                repo.set_game_players(chat_id, ",".join(players))
            await query.edit_message_text(f"🎮 O‘yinchilar: {len(players)}/{repo.get_setting('game.max_players','12')}")
            return
        await query.answer(f"Players: {len(players)}", show_alert=True)
        return

    if query.data.startswith("ract:"):
        parts = query.data.split(":")
        # ract:mode:chat_id:mode
        if parts[1] == "mode":
            chat_id = int(parts[2])
            mode = parts[3]
            if mode == "skip":
                game = repo.get_game(chat_id)
                if game:
                    repo.set_night_action(chat_id, game["day_no"], query.from_user.id, "skip")
                await query.edit_message_text("⏭ Skip qabul qilindi")
                return
            players = [r for r in repo.get_alive_roles(chat_id) if r["user_id"] != query.from_user.id]
            rows = [[InlineKeyboardButton(f"👤 {p['user_id']}", callback_data=f"ract:pick:{chat_id}:{mode}:{p['user_id']}")] for p in players[:12]]
            rows.append([InlineKeyboardButton("⏭ Skip", callback_data=f"ract:pick:{chat_id}:skip:0")])
            await query.edit_message_text("Kimni tanlaysiz?", reply_markup=InlineKeyboardMarkup(rows))
            return

        # ract:pick:chat_id:mode:target
        if parts[1] == "pick":
            chat_id = int(parts[2])
            mode = parts[3]
            target = int(parts[4])
            game = repo.get_game(chat_id)
            if not game:
                await query.edit_message_text("O‘yin topilmadi")
                return
            action = "skip" if mode == "skip" else f"{mode}:{target}"
            repo.set_night_action(chat_id, game["day_no"], query.from_user.id, action)
            await query.edit_message_text("✅ Nishon tanlandi")
            return

        # ract:mine:chat_id:slot
        if parts[1] == "mine":
            chat_id = int(parts[2])
            slot = int(parts[3])
            game = repo.get_game(chat_id)
            if not game:
                await query.edit_message_text("O‘yin topilmadi")
                return
            # 1 prize diamond, 1 money, 1 death
            mapping = ["diamond", "money", "death"]
            random.shuffle(mapping)
            outcome = mapping[slot - 1]
            if outcome == "diamond":
                gain = random.randint(1, 5)
                repo.add_diamonds(query.from_user.id, gain)
                repo.set_night_action(chat_id, game["day_no"], query.from_user.id, f"minegain:{gain}d")
                await query.edit_message_text(f"💎 Konchi yutug‘i: +{gain} olmos")
                return
            if outcome == "money":
                gain = random.randint(50, 250)
                repo.add_money(query.from_user.id, gain)
                repo.set_night_action(chat_id, game["day_no"], query.from_user.id, f"minegain:{gain}$")
                await query.edit_message_text(f"💰 Konchi yutug‘i: +{gain}$")
                return

            # death case -> mine protection check
            blocked, msg = apply_defense_pipeline(query.from_user.id, "mine")
            if blocked:
                repo.set_night_action(chat_id, game["day_no"], query.from_user.id, "mine:survive")
                await query.edit_message_text(msg)
            else:
                repo.set_dead(chat_id, query.from_user.id)
                repo.set_night_action(chat_id, game["day_no"], query.from_user.id, "mine:dead")
                await query.edit_message_text("☠️ Konchi noto‘g‘ri konni tanladi va o‘ldi")
            return


# ----- admin/owner panel interactive flow -----
async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    repo.ensure_user(q.from_user.id, q.from_user.username)
    me = repo.get_player(q.from_user.id)

    data = q.data

    if data == "panel:admin" and not is_admin_or_owner(me.role):
        await q.edit_message_text(no_permission_text())
        return
    if data == "panel:owner" and me.role != "owner":
        await q.edit_message_text(no_permission_text())
        return

    if data == "panel:profile":
        await q.edit_message_text(f"👤 PROFILE\nRole: {me.role}\nBalans: ${me.money} | 💎 {me.diamonds}")
        return

    if data == "panel:shop":
        await q.edit_message_text("🛒 SHOP\n[dynamic pricing + item toggles]")
        return

    if data == "panel:casino":
        await q.edit_message_text("🎰 CASINO\n/dicebet /roulette /blackjack /mines\n/chistory")
        return

    if data == "panel:stats":
        await q.edit_message_text("📊 STATS\nfoundation")
        return

    if data == "panel:admin":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Users", callback_data="ap:users"), InlineKeyboardButton("🏘 Groups", callback_data="ap:groups")],
            [InlineKeyboardButton("🎮 Active Games", callback_data="ap:games")],
            [InlineKeyboardButton("📊 Stats", callback_data="ap:stats"), InlineKeyboardButton("📢 Broadcast", callback_data="ap:broadcast")],
            [InlineKeyboardButton("📜 Logs", callback_data="ap:logs"), InlineKeyboardButton("💰 Economy", callback_data="ap:economy")],
            [InlineKeyboardButton("🔙 Back", callback_data="ap:back")],
        ])
        await q.edit_message_text("👑 ADMIN PANEL", reply_markup=kb)
        return

    if data == "panel:owner":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Shop Settings", callback_data="op:shop"), InlineKeyboardButton("💰 Price", callback_data="op:price")],
            [InlineKeyboardButton("👤 Buy Contact", callback_data="op:buy_contact"), InlineKeyboardButton("📢 Channels", callback_data="op:channels")],
            [InlineKeyboardButton("🎰 Casino Settings", callback_data="op:casino"), InlineKeyboardButton("🎮 Game Settings", callback_data="op:game")],
            [InlineKeyboardButton("🛡 Anti-Farm", callback_data="op:antifarm"), InlineKeyboardButton("🎬 Media", callback_data="op:media")],
            [InlineKeyboardButton("🧠 Role Texts", callback_data="op:role_texts")],
            [InlineKeyboardButton("🔙 Back", callback_data="op:back")],
        ])
        await q.edit_message_text("⚙️ OWNER PANEL", reply_markup=kb)
        return

    # Admin panel subflows
    admin_flows = {
        "ap:users": "👥 USERS\n[Search ID] [Search Username]\n[Ban] [Mute] [Warn]",
        "ap:groups": "🏘 GROUPS\nGroup analytics list",
        "ap:games": "🎮 ACTIVE GAMES\n[Skip Phase] [Pause] [Stop]",
        "ap:stats": "📊 Global stats",
        "ap:broadcast": "📢 BROADCAST\nUse /broadcast <text> (owner/admin)",
        "ap:logs": "📜 LOGS\n[Transactions] [Games] [Actions]",
        "ap:economy": "💰 ECONOMY OVERVIEW",
        "ap:back": "Back to /start",
    }
    if data in admin_flows:
        await q.edit_message_text(admin_flows[data])
        return

    # Owner panel subflows screen-by-screen
    owner_flows = {
        "op:shop": "🛒 SHOP SETTINGS\n[Items] [Premium] [Mystery Box] [Titles]",
        "op:price": "💰 PRICE SETTINGS\n/setting set shop.item.protection_price 200",
        "op:buy_contact": f"👤 BUY CONTACT\nCurrent: {repo.get_setting('text.buy_contact', '@payment_admin')}\nUse /setting set text.buy_contact @new",
        "op:channels": (
            "📢 CHANNELS\n"
            f"News: {repo.get_setting('text.news_channel', '@news')}\n"
            f"Official: {repo.get_setting('text.official_channel', '@official')}\n"
            "Use /setting set text.news_channel @..."
        ),
        "op:casino": "🎰 CASINO SETTINGS\n/setcasino casino.dice_mult 3.2\n/setcasino casino.blackjack_mult 2.1",
        "op:game": "🎮 GAME SETTINGS\n/setting set game.min_players 6\n/setting set game.turn_timer_sec 45",
        "op:antifarm": "🛡 ANTI-FARM\n/setting set antifarm.reward_mult 0.8\n/setting set antifarm.casino_rtp_mult 0.9",
        "op:media": "🎬 MEDIA\n(placeholder) upload flow: /media <night|day|court|gameover> with file",
        "op:role_texts": "🧠 ROLE TEXTS\n/setting set text.kill.don ...\n/setting set text.inactive.mafia ...",
        "op:back": "Back to /start",
    }
    if data in owner_flows:
        await q.edit_message_text(owner_flows[data])
        return


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("/stop faqat group")
        return

    allowed = False
    if me.role in {"admin", "owner"}:
        allowed = True
    elif me.role == "partner" and repo.can_partner_control(me.user_id, chat.id):
        member = await context.bot.get_chat_member(chat.id, me.user_id)
        allowed = member.status in {"administrator", "creator"}

    if not allowed:
        await update.message.reply_text(no_permission_text())
        return

    repo.delete_game(chat.id)
    await update.message.reply_text("🛑 O‘yin to‘xtatildi")


async def ginfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text("/ginfo group")
        return
    if me.role == "partner" and repo.can_partner_control(me.user_id, chat.id):
        pass
    elif me.role not in {"admin", "owner"}:
        await update.message.reply_text(no_permission_text())
        return
    g = repo.get_game(chat.id)
    if not g:
        await update.message.reply_text("Faol o‘yin yo‘q")
        return
    alive = len(repo.get_alive_roles(chat.id))
    await update.message.reply_text(f"Status: {g['status']} | Day: {g['day_no']} | Alive: {alive}")


# ----- owner/admin management -----
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role != "owner":
        await update.message.reply_text(no_permission_text())
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply qiling")
        return
    u = update.message.reply_to_message.from_user
    repo.ensure_user(u.id, u.username)
    repo.set_role(u.id, "admin")
    await update.message.reply_text("✅ Admin berildi")


async def unadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role != "owner":
        await update.message.reply_text(no_permission_text())
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply qiling")
        return
    u = update.message.reply_to_message.from_user
    repo.ensure_user(u.id, u.username)
    repo.set_role(u.id, "player")
    await update.message.reply_text("✅ Admin olib tashlandi")


async def owner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role != "owner":
        await update.message.reply_text(no_permission_text())
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply qiling")
        return
    u = update.message.reply_to_message.from_user
    repo.ensure_user(u.id, u.username)
    repo.set_role(me.user_id, "player")
    repo.set_role(u.id, "owner")
    await update.message.reply_text("✅ Owner transfer qilindi")


async def partnergroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role != "owner":
        await update.message.reply_text(no_permission_text())
        return
    if len(context.args) < 2:
        await update.message.reply_text("Format: /partnergroup <user_id> <chat_id>")
        return
    uid = parse_int(context.args[0])
    cid = parse_int(context.args[1])
    if uid is None or cid is None:
        await update.message.reply_text("user_id va chat_id son bo‘lishi kerak")
        return
    repo.ensure_user(uid)
    repo.set_role(uid, "partner")
    repo.add_partner_group(uid, cid)
    await update.message.reply_text("✅ Partner biriktirildi")


async def setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role != "owner":
        await update.message.reply_text(no_permission_text())
        return
    if len(context.args) < 2:
        await update.message.reply_text("/setting get <key> | /setting set <key> <value>")
        return
    mode = context.args[0]
    key = context.args[1]
    if mode == "get":
        await update.message.reply_text(f"{key} = {repo.get_setting(key, '<none>')}")
        return
    if mode == "set" and len(context.args) >= 3:
        value = " ".join(context.args[2:])
        repo.set_setting(key, value)
        await update.message.reply_text("✅ Updated")
        return
    await update.message.reply_text("Noto‘g‘ri format")


async def setcasino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if me.role != "owner":
        await update.message.reply_text(no_permission_text())
        return
    if len(context.args) < 2:
        await update.message.reply_text("/setcasino <key> <value>")
        return
    key, value = context.args[0], context.args[1]
    allowed = {
        "casino.dice_mult",
        "casino.blackjack_mult",
        "casino.roulette_color_mult",
        "casino.roulette_zero_mult",
        "casino.mines_base_mult",
    }
    if key not in allowed:
        await update.message.reply_text("Noto‘g‘ri key")
        return
    repo.set_setting(key, value)
    await update.message.reply_text("✅ Casino setting updated")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin/Owner broadcast helper to active game chats."""
    me = await _ensure(update)
    if me.role not in {"admin", "owner"}:
        await update.message.reply_text(no_permission_text())
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Format: /broadcast <xabar>")
        return
    chats = repo.list_game_chats()
    sent = 0
    for r in chats:
        try:
            await context.bot.send_message(chat_id=r["chat_id"], text=f"📢 Broadcast:\n{text}")
            sent += 1
        except Exception as exc:  # network/permission issues should not break full send
            logger.warning("Broadcast failed to %s: %s", r["chat_id"], exc)
    await update.message.reply_text(f"✅ Broadcast yuborildi: {sent} ta chat")


async def helpme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    text = (
        "📘 Commands\\n"
        "Game: /newgame /startgame /nextphase /vote /myrole /action /nightui /stop\\n"
        "Economy: /money /send /give /unmoney /unsend /ungive\\n"
        "Casino: /dicebet /roulette /blackjack /mines /chistory\\n"
        "Owner: /admin /unadmin /owner /partnergroup /setting /setcasino\\n"
        "System: /broadcast /roleengine /rolecard /itemtoggle"
    )
    await update.message.reply_text(text)


# ----- role engine docs -----
async def roleengine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    lines = ["🎭 FULL ROLE ENGINE", "", "✅ PHASE1 MVP TOP12:"]
    for role in PHASE1_MVP_ROLES:
        spec = ROLE_SPECS.get(role, {})
        lines.append(f"- {role}: team={spec.get('team','-')}, ui={spec.get('ui','-')}")
    lines.append("")
    lines.append("🔹 PHASE2 ADVANCED:")
    lines.append(", ".join(PHASE2_ADVANCED_ROLES))
    lines.append("")
    lines.append("Priority: BLOCK > MODIFY > CHECK > TRAP > KILL > DEFENSE > STATUS > HEAL > RANDOM")
    lines.append("Universal: [⏭ O‘tkazib yuborish], timer = " + repo.get_setting("game.turn_timer_sec", "30") + " sec")
    await update.message.reply_text("\n".join(lines[:120]))


# ----- casino handlers -----
async def dicebet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE or not context.args:
        await update.message.reply_text("/dicebet <bet> (private)")
        return
    bet = parse_int(context.args[0])
    if bet is None:
        await update.message.reply_text("Bet son bo‘lishi kerak")
        return
    min_bet, max_bet, level = get_bet_limits(me)
    if bet <= 0 or me.money < bet or bet < min_bet or bet > max_bet:
        await update.message.reply_text(f"Bet limiti: {level} => {min_bet}$..{max_bet}$")
        return
    roll = random.randint(1, 6)
    win = roll >= 5
    mult = float(repo.get_setting("casino.dice_mult", "3.0")) * effective_rtp_multiplier(me.user_id)
    repo.add_money(me.user_id, -bet)
    payout = int(bet * mult) if win else 0
    if payout:
        repo.add_money(me.user_id, payout)
    repo.add_casino_history(me.user_id, "dice", bet, payout, f"roll={roll}")
    await update.message.reply_text(f"🎲 {roll} | payout={payout}$")


async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE or len(context.args) < 2:
        await update.message.reply_text("/roulette <bet> <red|black|0>")
        return
    bet = parse_int(context.args[0])
    if bet is None:
        await update.message.reply_text("Bet son bo‘lishi kerak")
        return
    pick = context.args[1].lower()
    min_bet, max_bet, level = get_bet_limits(me)
    if pick not in {"red", "black", "0"} or bet <= 0 or me.money < bet or bet < min_bet or bet > max_bet:
        await update.message.reply_text(f"Noto‘g‘ri parametr. Limit: {level} => {min_bet}$..{max_bet}$")
        return
    n = random.randint(0, 36)
    color = "0" if n == 0 else ("red" if n % 2 else "black")
    win = pick == color
    repo.add_money(me.user_id, -bet)
    mult = float(repo.get_setting("casino.roulette_zero_mult", "14.0")) if pick == "0" else float(
        repo.get_setting("casino.roulette_color_mult", "2.0")
    )
    mult *= effective_rtp_multiplier(me.user_id)
    payout = int(bet * mult) if win else 0
    if payout:
        repo.add_money(me.user_id, payout)
    repo.add_casino_history(me.user_id, "roulette", bet, payout, f"spin={n}:{color}")
    await update.message.reply_text(f"🎡 {n} ({color}) | payout={payout}$")


async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE or not context.args:
        await update.message.reply_text("/blackjack <bet>")
        return
    bet = parse_int(context.args[0])
    if bet is None:
        await update.message.reply_text("Bet son bo‘lishi kerak")
        return
    min_bet, max_bet, level = get_bet_limits(me)
    if bet <= 0 or me.money < bet or bet < min_bet or bet > max_bet:
        await update.message.reply_text(f"Bet limiti: {level} => {min_bet}$..{max_bet}$")
        return

    def draw() -> int:
        return random.choice([2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 11])

    p, d = draw() + draw(), draw() + draw()
    while p < 17:
        p += draw()
    while d < 17:
        d += draw()
    win = p <= 21 and (d > 21 or p > d)

    repo.add_money(me.user_id, -bet)
    mult = float(repo.get_setting("casino.blackjack_mult", "2.0")) * effective_rtp_multiplier(me.user_id)
    payout = int(bet * mult) if win else 0
    if payout:
        repo.add_money(me.user_id, payout)
    repo.add_casino_history(me.user_id, "blackjack", bet, payout, f"p={p},d={d}")
    await update.message.reply_text(f"🃏 P={p} D={d} | payout={payout}$")


async def mines(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    if update.effective_chat.type != ChatType.PRIVATE or len(context.args) < 2:
        await update.message.reply_text("/mines <bet> <1..5>")
        return
    bet = parse_int(context.args[0])
    mines_count = parse_int(context.args[1])
    if bet is None or mines_count is None:
        await update.message.reply_text("Bet va mina soni son bo‘lishi kerak")
        return
    min_bet, max_bet, level = get_bet_limits(me)
    if bet <= 0 or mines_count < 1 or mines_count > 5 or me.money < bet or bet < min_bet or bet > max_bet:
        await update.message.reply_text(f"Noto‘g‘ri parametr. Limit: {level} => {min_bet}$..{max_bet}$")
        return
    safe = random.randint(1, 25) <= 25 - mines_count
    repo.add_money(me.user_id, -bet)
    base = float(repo.get_setting("casino.mines_base_mult", "1.35")) * effective_rtp_multiplier(me.user_id)
    payout = int(bet * (base + mines_count * 0.25)) if safe else 0
    if payout:
        repo.add_money(me.user_id, payout)
    repo.add_casino_history(me.user_id, "mines", bet, payout, f"mines={mines_count},safe={safe}")
    await update.message.reply_text(f"💣 {'SAFE' if safe else 'BOOM'} | payout={payout}$")


async def chistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    me = await _ensure(update)
    rows = repo.casino_last(me.user_id, 10)
    if not rows:
        await update.message.reply_text("Tarix bo‘sh")
        return
    await update.message.reply_text("\n".join([f"{r['game']} | bet={r['bet']} | payout={r['payout']}" for r in rows]))


# ----- utility commands -----
async def itemtoggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    if len(context.args) < 2:
        await update.message.reply_text("/itemtoggle <item> <on|off>")
        return
    item = context.args[0].lower()
    enabled = 1 if context.args[1].lower() == "on" else 0
    repo.set_item_toggle(update.effective_user.id, item, enabled)
    await update.message.reply_text("✅ Item toggle updated")


async def rolecard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure(update)
    if not context.args:
        await update.message.reply_text("/rolecard <RoleName>")
        return
    role = " ".join(context.args)
    spec = ROLE_SPECS.get(role)
    if not spec:
        await update.message.reply_text("Role topilmadi")
        return
    await update.message.reply_text(
        f"🎭 {role}\nTeam: {spec['team']}\nGoal: {spec['goal']}\nUI Type: {spec['ui']}\n"
        f"Keywords: interactive role system / button-based gameplay / dynamic role actions"
    )


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN set qilinmagan")

    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", helpme))
    app.add_handler(CommandHandler("helpme", helpme))
    app.add_handler(CommandHandler("money", money))
    app.add_handler(CommandHandler("send", send))
    app.add_handler(CommandHandler("give", give))
    app.add_handler(CommandHandler("unmoney", unmoney))
    app.add_handler(CommandHandler("unsend", unsend))
    app.add_handler(CommandHandler("ungive", ungive))
    app.add_handler(CommandHandler("ginfo", ginfo))

    # Game
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("nextphase", nextphase))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("myrole", myrole))
    app.add_handler(CommandHandler("action", action))
    app.add_handler(CommandHandler("nightui", nightui))
    app.add_handler(CommandHandler("stop", stop))

    # Role engine docs
    app.add_handler(CommandHandler("roleengine", roleengine))
    app.add_handler(CommandHandler("rolecard", rolecard))

    # Management
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("unadmin", unadmin_cmd))
    app.add_handler(CommandHandler("owner", owner_cmd))
    app.add_handler(CommandHandler("partnergroup", partnergroup))
    app.add_handler(CommandHandler("setting", setting))
    app.add_handler(CommandHandler("setcasino", setcasino))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Casino
    app.add_handler(CommandHandler("dicebet", dicebet))
    app.add_handler(CommandHandler("roulette", roulette))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("mines", mines))
    app.add_handler(CommandHandler("chistory", chistory))

    # Items
    app.add_handler(CommandHandler("itemtoggle", itemtoggle))

    # Callbacks
    app.add_handler(CallbackQueryHandler(panel_callback, pattern=r"^(panel:|ap:|op:)"))
    app.add_handler(CallbackQueryHandler(game_callback, pattern=r"^(join:|players:|ract:).+"))

    logger.info("Bot ishga tushdi")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
