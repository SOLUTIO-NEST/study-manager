import os

from dotenv import load_dotenv


load_dotenv()

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"

NOTION_TOKEN = os.environ["NOTION_TOKEN"]


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }