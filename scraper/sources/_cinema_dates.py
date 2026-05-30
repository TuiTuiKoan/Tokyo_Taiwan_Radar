"""共通電影院日期／時刻解析函式模組。"""
from datetime import datetime, timezone
from typing import Optional
import re


def parse_japanese_date(text: str) -> Optional[datetime]:
    """解析「YYYY年MM月DD日」或「MM月DD日」，含全形數字。回傳 UTC midnight datetime。"""
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 嘗試 YYYY年MM月DD日
    m = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    # 嘗試 MM月DD日（無年份，用當年）
    m = re.search(r"(\d{1,2})月\s*(\d{1,2})日", text)
    if m:
        try:
            now = datetime.now(timezone.utc)
            return datetime(now.year, int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None  # Date-Parser Exhaustive Return Guard


def parse_date_range(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """解析「MM/DD～MM/DD」或「YYYY.MM.DD～MM.DD」等範圍，回傳 (start, end) UTC midnight。
    用 re.findall 取所有日期，頭尾各一。所有分支明確 return None, None。"""
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 嘗試 YYYY年MM月DD日 ～ YYYY年MM月DD日
    dates = re.findall(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if len(dates) >= 2:
        try:
            start = datetime(int(dates[0][0]), int(dates[0][1]), int(dates[0][2]), tzinfo=timezone.utc)
            end = datetime(int(dates[-1][0]), int(dates[-1][1]), int(dates[-1][2]), tzinfo=timezone.utc)
            return start, end
        except ValueError:
            pass
    if len(dates) == 1:
        try:
            start = datetime(int(dates[0][0]), int(dates[0][1]), int(dates[0][2]), tzinfo=timezone.utc)
            return start, None
        except ValueError:
            pass
    # 嘗試 M/D 或 MM/DD（含全形斜線）
    dates_md = re.findall(r"(\d{1,2})[/／](\d{1,2})", text)
    if len(dates_md) >= 1:
        now = datetime.now(timezone.utc)
        try:
            start = datetime(now.year, int(dates_md[0][0]), int(dates_md[0][1]), tzinfo=timezone.utc)
            end = None
            if len(dates_md) >= 2:
                end = datetime(now.year, int(dates_md[-1][0]), int(dates_md[-1][1]), tzinfo=timezone.utc)
            return start, end
        except ValueError:
            pass
    return None, None  # Date-Parser Exhaustive Return Guard


def extract_showtimes(text: str) -> Optional[str]:
    """從文字抽出 HH:MM 時刻清單，回傳 business_hours 字串（e.g. '10:30／14:00／18:30'）。"""
    text = text.translate(str.maketrans("０１２３４５６７８９：", "0123456789:"))
    times = re.findall(r"\b(\d{1,2}:\d{2})\b", text)
    if times:
        return "／".join(times)
    return None
