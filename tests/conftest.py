"""Гарантирует, что BOT_TOKEN задан до импорта main."""
import os

os.environ.setdefault("BOT_TOKEN", "test-token-for-ci")
