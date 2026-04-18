import os
import sys
import tempfile
import types
import unittest

# Minimal stubs so `main` can be imported without external telegram package in CI.
telegram = types.ModuleType("telegram")
telegram.InlineKeyboardButton = object
telegram.InlineKeyboardMarkup = object
telegram.Update = object
sys.modules["telegram"] = telegram

telegram_constants = types.ModuleType("telegram.constants")
telegram_constants.ChatType = types.SimpleNamespace(PRIVATE="private")
sys.modules["telegram.constants"] = telegram_constants

telegram_ext = types.ModuleType("telegram.ext")
telegram_ext.Application = object
telegram_ext.CallbackQueryHandler = object
telegram_ext.CommandHandler = object
telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
sys.modules["telegram.ext"] = telegram_ext

import main


class RepoAndItemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.repo = main.Repo(self.tmp.name)
        # patch global repo used by helper functions
        main.repo = self.repo

        self.repo.ensure_user(1, "u1")
        self.repo.ensure_user(2, "u2")

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except FileNotFoundError:
            pass

    def test_parse_int(self):
        self.assertEqual(main.parse_int("12"), 12)
        self.assertIsNone(main.parse_int("x"))

    def test_transfer_money(self):
        ok, _ = self.repo.transfer_money(1, 2, 100)
        self.assertTrue(ok)
        self.assertEqual(self.repo.get_player(1).money, 900)
        self.assertEqual(self.repo.get_player(2).money, 1100)

    def test_bet_limits(self):
        p = self.repo.get_player(1)
        self.assertEqual(main.get_bet_limits(p), (50, 1000, "Normal"))
        self.repo.add_money(1, 5000)
        p2 = self.repo.get_player(1)
        self.assertEqual(main.get_bet_limits(p2), (100, 5000, "VIP"))

    def test_defense_pipeline_protection_blocks_kill(self):
        self.repo.add_item(2, "himoya", 1)
        blocked, msg = main.apply_defense_pipeline(2, "kill")
        self.assertTrue(blocked)
        self.assertIn("bloklandi", msg)
        self.assertEqual(self.repo.get_item(2, "himoya")["count"], 0)

    def test_effective_rtp_reduced_on_high_win_streak(self):
        # produce 6 winning records
        for _ in range(6):
            self.repo.add_casino_history(1, "dice", 100, 300, "win")
        self.assertLess(main.effective_rtp_multiplier(1), 1.0)


if __name__ == "__main__":
    unittest.main()
