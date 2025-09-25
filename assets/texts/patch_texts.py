# -*- coding: utf-8 -*-
"""
Simplified CSV patcher:
- UPDATES: original_key -> (new_key, new_en, new_zh)
- INSERTS: previous_key  -> (key, en, zh)  [always inserted AFTER previous_key; None -> at file start]
- Order: apply all UPDATES, then apply INSERTS in the order listed.
- Preserves CRLF between rows and LF inside quoted fields.
"""

import csv
import io
import os
from typing import Dict, List, Tuple, Optional

# ------------- CONFIG ---------------------------------------------------------
INPUT_PATH  = "texts.csv"   # your file
OUTPUT_PATH = None                        # None -> overwrite INPUT_PATH (writes .bak once)

# 1) Updates: original_key -> (new_key, new_en, new_zh)
UPDATES: Dict[str, Tuple[str, str, str]] = {
    # example (leave empty if not needed):
    # "OLD_KEY": ("NEW_KEY", "New English", "新的中文"),
    
}

# 2) Inserts: previous_key -> (key, en, zh)
# Always inserted AFTER previous_key; if previous_key is None, insert at the very beginning (index 0).
INSERTS: List[Tuple[Optional[str], Tuple[str, str, str]]] = [
    # Then: WU10–WU23 chain inserted AFTER 9JVP (Advanced Wisdom)
    ("9JVP", ("WU10", "Pillage Mastery\n \nIncreases bounty collected by [color=GOLD]16%[/color].",
                     "劫掠专精\n\n获取的赏金增加 [color=GOLD]16%[/color] 。")),
    ("WU10", ("WU11", "Fortified Will\n \nDecreases duration of debuffs on your towers by [color=GOLD]9%[/color].",
                     "坚韧意志\n\n你的防御塔受到的负面状态持续时间降低 [color=GOLD]9%[/color] 。")),
    ("WU11", ("WU12", "Inner Focus\n \nIncreases duration of your tower's buffs by [color=GOLD]6.5%[/color].",
                     "内在专注\n\n增加由你的防御塔施加的增益效果持续时间 [color=GOLD]6.5%[/color] 。")),
    ("WU12", ("WU13", "Bond of Unity\n \nIncreases starting lives by [color=GOLD]20%[/color].",
                     "团结之契\n\n起始生命数增加 [color=GOLD]20%[/color] 。")),
    ("WU13", ("WU14", "Foundation of Knowledge\n \nAll towers start with [color=GOLD]30[/color] bonus experience.",
                     "知识之基\n\n所有防御塔初始拥有 [color=GOLD]30[/color] 点奖励经验。")),
    ("WU14", ("WU15", "Deadly Strikes\n \nIncreases attack and spell critical damage of all towers by [color=GOLD]17.5%[/color].",
                     "致命打击\n\n所有防御塔的物理暴击伤害和法术暴击伤害增加 [color=GOLD]17.5%[/color] 。")),
    ("WU15", ("WU16", "Fortune's Favor\n \nIncreases item quality of all towers by [color=GOLD]6.5%[/color].",
                     "命运眷顾\n\n所有防御塔的物品品质提升 [color=GOLD]6.5%[/color] 。")),
    ("WU16", ("WU17", "Challenge Conqueror\n \nIncreases damage dealt to Challenge enemies by [color=GOLD]10%[/color].",
                     "挑战征服者\n\n对“挑战”敌人的伤害提高 [color=GOLD]10%[/color] 。")),
    ("WU17", ("WU18", "Master of Destruction\n \nIncreases total damage dealt by towers by [color=GOLD]2.5%[/color].",
                     "毁灭大师\n\n所有防御塔造成的总伤害提高 [color=GOLD]2.5%[/color] 。")),
    ("WU18", ("WU19", "Advanced Optics\n \nIncreases normal attack range of all towers by [color=GOLD]25[/color].",
                     "光学专精\n\n所有防御塔的普通攻击射程增加 [color=GOLD]25[/color] 。")),
    ("WU19", ("WU20", "Elemental Overload\n \nIncreases maximum element level by [color=GOLD]2[/color] (unaffected by Wisdom Upgrade effectiveness).",
                     "元素超载\n\n元素最大等级增加 [color=GOLD]2[/color]（不受智慧升级效果影响）。")),
    ("WU20", ("WU21", "Pinnacle of Power\n \nIncreases maximum tower level by [color=GOLD]2[/color] (unaffected by Wisdom Upgrade effectiveness).",
                     "力量巅峰\n\n防御塔最大等级增加 [color=GOLD]2[/color]（不受智慧升级效果影响）。")),
    ("WU21", ("WU22", "Advanced Synergy\n \nIncreases effectiveness of other Wisdom Upgrades by [color=GOLD]6%[/color] (unaffected by Wisdom Upgrade effectiveness).",
                     "协同专精\n\n其他智慧升级的效果提高 [color=GOLD]6%[/color]（不受智慧升级效果影响）。")),
    ("WU22", ("WU23", "The Path of Ascension\n \nIncreases effectiveness of other Wisdom Upgrades by [color=GOLD]0.1%[/color] for every player level unspent on upgrades (unaffected by Wisdom Upgrade effectiveness).",
                     "飞升之道\n\n每有 1 点未用于升级的玩家等级，其他智慧升级的效果提高 [color=GOLD]0.1%[/color]（不受智慧升级效果影响）。")),
    
    ("WISDOM_UPGRADES_AVAILABLE", ("WISDOM_EFFECTIVENESS_BONUS", "Wisdom effectiveness:", "智慧强化效果：")),
]
# -----------------------------------------------------------------------------


def read_text(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def write_text(path: str, text: str) -> None:
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def split_rows_crlf(file_text: str) -> List[str]:
    """Split by CRLF only (embedded LFs remain inside fields)."""
    return file_text.split("\r\n")


def join_rows_crlf(rows: List[str]) -> str:
    return "\r\n".join(rows)


def parse_row_csv(row_text: str) -> List[str]:
    sio = io.StringIO(row_text)
    r = csv.reader(sio)
    return next(r)


def make_row_csv(fields: List[str]) -> str:
    """Serialize fields to a CSV row string WITHOUT trailing row terminator."""
    out = io.StringIO()
    w = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="")
    w.writerow(fields)
    return out.getvalue()


def map_key_to_row_index(rows: List[str]) -> Dict[str, int]:
    mapping = {}
    for i, row in enumerate(rows):
        if not row.strip():
            continue
        try:
            fields = parse_row_csv(row)
        except Exception:
            continue
        if fields:
            mapping[fields[0]] = i
    return mapping


def apply_updates(rows: List[str], updates: Dict[str, Tuple[str, str, str]]) -> List[str]:
    if not updates:
        return rows
    updated = rows[:]
    key_to_idx = map_key_to_row_index(updated)
    for old_key, (new_key, en, zh) in updates.items():
        if old_key not in key_to_idx:
            raise SystemExit(f"[update] key not found: {old_key}")
        idx = key_to_idx[old_key]
        # prevent accidental collision if new_key already exists at a different row
        if new_key != old_key and new_key in key_to_idx and key_to_idx[new_key] != idx:
            raise SystemExit(f"[update] new_key already exists at a different row: {new_key}")
        updated[idx] = make_row_csv([new_key, en, zh])
        # refresh map for potential chained updates
        key_to_idx = map_key_to_row_index(updated)
        print(f"[update] {old_key} -> {new_key} at row index {idx}")
    return updated


def apply_inserts(rows: List[str], inserts: List[Tuple[Optional[str], Tuple[str, str, str]]]) -> List[str]:
    if not inserts:
        return rows
    updated = rows[:]
    key_to_idx = map_key_to_row_index(updated)
    for prev_key, (key, en, zh) in inserts:
        if key in key_to_idx:
            raise SystemExit(f"[insert] key already exists: {key}")
        if prev_key is None:
            insert_idx = 0
        else:
            if prev_key not in key_to_idx:
                raise SystemExit(f"[insert] previous_key not found: {prev_key}")
            insert_idx = key_to_idx[prev_key] + 1  # always AFTER previous_key
        updated[insert_idx:insert_idx] = [make_row_csv([key, en, zh])]
        # refresh map so later inserts can chain off newly inserted keys
        key_to_idx = map_key_to_row_index(updated)
        print(f"[insert] {key} after {prev_key if prev_key else '<START>'} at row index {insert_idx}")
    return updated


def main():
    text = read_text(INPUT_PATH)
    rows = split_rows_crlf(text)

    # 1) Apply updates
    rows = apply_updates(rows, UPDATES)

    # 2) Apply inserts
    rows = apply_inserts(rows, INSERTS)

    out_text = join_rows_crlf(rows)

    # Write result
    if OUTPUT_PATH:
        write_text(OUTPUT_PATH, out_text)
        print(f"[write] Wrote {OUTPUT_PATH}")
    else:
        bak = INPUT_PATH + ".bak"
        if not os.path.exists(bak):
            write_text(bak, text)
            print(f"[write] Backup written: {bak}")
        write_text(INPUT_PATH, out_text)
        print(f"[write] Updated in-place: {INPUT_PATH}")


if __name__ == "__main__":
    main()
