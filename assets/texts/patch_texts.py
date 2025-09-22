# -*- coding: utf-8 -*-
"""
Patch a CSV in-place (or to a new file) by key range (e.g., KYHF..WU23),
with modes to UPDATE existing rows or INSERT at a specific line (including LF and CRLF).

"""

import argparse
import csv
import io
import os
from typing import List, Dict

# ----------------------- FULL KEY ORDER (0..23) -------------------------------
full = [
    (0,  "KYHF", "Advanced Fortune"),
    (1,  "EAF9", "Element Mastery"),
    (2,  "OFOF", "Swiftness Mastery"),
    (3,  "VJZ2", "Combat Mastery"),
    (4,  "P81J", "Mastery of Pain"),
    (5,  "L6Z5", "Advanced Sorcery"),
    (6,  "S0T2", "Mastery of Magic"),
    (7,  "2GFC", "Mastery of Logistics"),
    (8,  "Z13P", "Loot Mastery"),
    (9,  "9JVP", "Advanced Wisdom"),
    (10, "WU10", "Pillage Mastery"),
    (11, "WU11", "Fortified Will"),
    (12, "WU12", "Inner Focus"),
    (13, "WU13", "Bond of Unity"),
    (14, "WU14", "Foundation of Knowledge"),
    (15, "WU15", "Deadly Strikes"),
    (16, "WU16", "Fortune's Favor"),
    (17, "WU17", "Challenge Conqueror"),
    (18, "WU18", "Master of Destruction"),
    (19, "WU19", "Advanced Optics"),
    (20, "WU20", "Elemental Overload"),
    (21, "WU21", "Pinnacle of Power"),
    (22, "WU22", "Advanced Synergy"),
    (23, "WU23", "The Art of Ascension"),
]
id_to_key = {i: k for i, k, _ in full}
id_to_name = {i: n for i, _, n in full}
KEYS_ORDER = [k for _, k, _ in full]

# --- English tooltips (exact formatting preserved) by id ----------------------
id_to_en_tooltip = {
0:  "Advanced Fortune\n \nIncreases trigger changes of all towers by [color=GOLD]10%[/color]",
1:  "Element Mastery\n \nIncreases starting knowledge tomes by [color=GOLD]40[/color].",
2:  "Swiftness Mastery\n \nIncreases attack speed of all towers by [color=GOLD]7%[/color].",
3:  "Combat Mastery\n \nIncreases base attack damage of all towers by [color=GOLD]8%[/color].",
4:  "Mastery of Pain\n \nIncreases attack and spell critical strike chance of all towers by [color=GOLD]4%[/color].",
5:  "Advanced Sorcery\n \nIncreases spell damage of all towers by [color=GOLD]10%[/color].",
6:  "Mastery of Magic\n \nIncreases mana pool and regeneration of all towers by [color=GOLD]20%[/color].",
7:  "Mastery of Logistics\n \nIncreases food limit by [color=GOLD]16[/color].",
8:  "Loot Mastery\n \nIncreases item chance of all towers by [color=GOLD]12%[/color].",
9:  "Advanced Wisdom\n \nIncreases experience gain of all towers by [color=GOLD]20%[/color].",
10: "Pillage Mastery\n \nIncreases bounty collected by [color=GOLD]16%[/color].",
11: "Fortified Will\n \nDecreases duration of debuffs on all towers by [color=GOLD]7.5%[/color].",
12: "Inner Focus\n \nIncreases duration of buffs on all towers by [color=GOLD]6%[/color].",
13: "Bond of Unity\n \nIncreases starting lives by [color=GOLD]20%[/color].",
14: "Foundation of Knowledge\n \nAll tower start with [color=GOLD]30[/color] experience.",
15: "Deadly Strikes\n \nIncreases attack and spell critical damage of all towers by [color=GOLD]17.5%[/color].",
16: "Fortune's Favor\n \nIncreases item quality of all towers by [color=GOLD]6.5%[/color].",
17: "Challenge Conqueror\n \nIncreases damage dealt to Challenge enemies by [color=GOLD]8%[/color].",
18: "Master of Destruction\n \nIncreases total damage dealt by towers by [color=GOLD]2%[/color].",
19: "Advanced Optics\n \nIncreases normal attack range of all towers by [color=GOLD]20[/color].",
20: "Elemental Overload\n \nIncreases maximum element level by [color=GOLD]2[/color] (unaffected by Wisdom Upgrade effectiveness).",
21: "Pinnacle of Power\n \nIncreases maximum tower level by [color=GOLD]2[/color] (unaffected by Wisdom Upgrade effectiveness).",
22: "Advanced Synergy\n \nIncreases effectiveness of other Wisdom Upgrades by [color=GOLD]6%[/color] (unaffected by Wisdom Upgrade effectiveness).",
23: "The Art of Ascension\n \nIncreases effectiveness of other Wisdom Upgrades by [color=GOLD]0.1%[/color] for every player level unspent on upgrades (unaffected by Wisdom Upgrade effectiveness).",
}

# --- Chinese (existing for 0..9) ---------------------------------------------
existing_zh = {
"KYHF": "幸运专精\n\n所有防御塔的触发几率增加 [color=GOLD]10%[/color] 。",
"EAF9": "元素专精\n\n起始知识点数增加 [color=GOLD]40[/color] 点。",
"OFOF": "迅捷专精\n\n所有防御塔的攻击速度增加 [color=GOLD]7%[/color] 。",
"VJZ2": "战斗专精\n\n所有防御塔的基础攻击力增加 [color=GOLD]8%[/color] 。",
"P81J": "苦痛专精\n\n所有防御塔的物理暴击几率和法术暴击几率增加 [color=GOLD]4%[/color] 。",
"L6Z5": "法术专精\n\n所有防御塔的法术伤害增加 [color=GOLD]10%[/color] 。",
"S0T2": "法力专精\n\n所有防御塔的法力值和法力回复增加 [color=GOLD]20%[/color] 。",
"2GFC": "后勤专精\n\n初始食物上限增加 [color=GOLD]16[/color] 点。",
"Z13P": "掠夺专精\n\n所有防御塔的物品获取率增加 [color=GOLD]12%[/color] 。",
"9JVP": "智慧专精\n\n所有防御塔的经验值获取率增加 [color=GOLD]20%[/color] 。",
}

# --- Chinese (new for 10..23) ------------------------------------------------
new_zh = {
"WU10": "劫掠专精\n\n获取的赏金增加 [color=GOLD]16%[/color] 。",
"WU11": "坚韧意志\n\n所有防御塔受到的负面状态持续时间降低 [color=GOLD]7.5%[/color] 。",
"WU12": "内在专注\n\n所有防御塔的增益状态持续时间增加 [color=GOLD]6%[/color] 。",
"WU13": "团结之契\n\n起始生命数增加 [color=GOLD]20%[/color] 。",
"WU14": "知识之基\n\n所有防御塔初始拥有 [color=GOLD]30[/color] 点经验。",
"WU15": "致命打击\n\n所有防御塔的物理暴击伤害和法术暴击伤害增加 [color=GOLD]17.5%[/color] 。",
"WU16": "命运眷顾\n\n所有防御塔的物品品质提升 [color=GOLD]6.5%[/color] 。",
"WU17": "挑战征服者\n\n对“挑战”敌人的伤害提高 [color=GOLD]8%[/color] 。",
"WU18": "毁灭大师\n\n所有防御塔造成的总伤害提高 [color=GOLD]2%[/color] 。",
"WU19": "光学专精\n\n所有防御塔的普通攻击射程增加 [color=GOLD]20[/color] 。",
"WU20": "元素超载\n\n元素最大等级增加 [color=GOLD]2[/color]（不受智慧升级效果影响）。",
"WU21": "力量巅峰\n\n防御塔最大等级增加 [color=GOLD]2[/color]（不受智慧升级效果影响）。",
"WU22": "协同专精\n\n其他智慧升级的效果提高 [color=GOLD]6%[/color]（不受智慧升级效果影响）。",
"WU23": "飞升之道\n\n每有 1 点未用于升级的玩家等级，其他智慧升级的效果提高 [color=GOLD]0.1%[/color]（不受智慧升级效果影响）。",
}

# Build EN/ZH by KEY (not by id)
EN_BY_KEY: Dict[str, str] = { id_to_key[i]: en for i, en in id_to_en_tooltip.items() }
ZH_BY_KEY: Dict[str, str] = { **existing_zh, **new_zh }

# -----------------------------------------------------------------------------


def read_text(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def write_text(path: str, text: str) -> None:
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def split_rows_crlf(file_text: str) -> List[str]:
    """Split by CRLF only. Embedded LFs remain inside fields."""
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


def cumulative_visual_starts(rows: List[str]) -> List[int]:
    """
    Start line (1-based) for each row, counting:
      - row.count('\\n') for embedded LFs
      - +1 for the CRLF row end
    """
    result = []
    current = 1
    for row in rows:
        result.append(current)
        current += row.count("\n") + 1
    return result


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


def slice_keys(start_key: str, end_key: str) -> List[str]:
    if start_key not in KEYS_ORDER:
        raise SystemExit(f"Unknown start key: {start_key}")
    if end_key not in KEYS_ORDER:
        raise SystemExit(f"Unknown end key: {end_key}")
    i = KEYS_ORDER.index(start_key)
    j = KEYS_ORDER.index(end_key)
    if j < i:
        raise SystemExit("end_key must not precede start_key in KEYS_ORDER.")
    return KEYS_ORDER[i:j+1]


def build_rows_for_keys(keys: List[str]) -> Dict[str, str]:
    """Build {key: csv_row_string} for the given keys. Requires EN and ZH content."""
    missing_en = [k for k in keys if k not in EN_BY_KEY]
    missing_zh = [k for k in keys if k not in ZH_BY_KEY]
    if missing_en:
        raise SystemExit("Missing English content for: " + ", ".join(missing_en))
    if missing_zh:
        # Fallback: produce a placeholder that clearly stands out
        for k in missing_zh:
            ZH_BY_KEY[k] = id_to_name[full[KEYS_ORDER.index(k)][0]] + "\n\n(缺少翻译)"
    out = {}
    for k in keys:
        out[k] = make_row_csv([k, EN_BY_KEY[k], ZH_BY_KEY[k]])
    return out


def find_row_index_by_visual_line(starts: List[int], target_line: int) -> int:
    """Return the row index whose start line equals target_line; else -1."""
    for idx, ln in enumerate(starts):
        if ln == target_line:
            return idx
    return -1


def run(
    input_path: str,
    output_path: str,
    mode: str,
    start_key: str,
    end_key: str,
    target_line: int = None,
    position: str = 'after',
    validate_line: bool = True,
    backup: bool = True
):
    text = read_text(input_path)
    rows = split_rows_crlf(text)
    key_to_idx = map_key_to_row_index(rows)
    starts = cumulative_visual_starts(rows)

    # Determine key range & build new rows
    keys = slice_keys(start_key, end_key)
    new_rows_map = build_rows_for_keys(keys)
    new_rows_ordered = [new_rows_map[k] for k in keys]

    # Detect contiguous existing block
    existing_indices = []
    all_present = True
    for k in keys:
        if k in key_to_idx:
            existing_indices.append(key_to_idx[k])
        else:
            all_present = False
            break
    contiguous = False
    if all_present:
        existing_indices_sorted = sorted(existing_indices)
        contiguous = all(
            existing_indices_sorted[i] + 1 == existing_indices_sorted[i+1]
            for i in range(len(existing_indices_sorted)-1)
        )

    if mode == "auto":
        mode_to_do = "update" if (all_present and contiguous) else "insert"
    else:
        mode_to_do = mode

    if mode_to_do == "update":
        if not all_present or not contiguous:
            raise SystemExit("Cannot update: specified keys are not present as a contiguous block.")
        start_idx = min(existing_indices)
        if validate_line and target_line is not None:
            actual_line = starts[start_idx]
            if actual_line != target_line:
                raise SystemExit(f"Line mismatch: intended {target_line}, actual {actual_line}. Aborting.")
        updated = rows[:]
        for offset, new_row in enumerate(new_rows_ordered):
            updated[start_idx + offset] = new_row
        out_text = join_rows_crlf(updated)

        if output_path:
            write_text(output_path, out_text)
            print(f"[UPDATE] Wrote {output_path}")
        else:
            if backup:
                bak = input_path + ".bak"
                if not os.path.exists(bak):
                    write_text(bak, text)
                    print(f"[UPDATE] Backup written: {bak}")
            write_text(input_path, out_text)
            print(f"[UPDATE] Updated in-place: {input_path}")
        return

    if mode_to_do == "insert":
        if target_line is None:
            raise SystemExit("Insert mode requires --target-line (1-based visual line).")
        insert_idx = find_row_index_by_visual_line(starts, target_line)
        if insert_idx < 0:
            raise SystemExit(f"No row starts at visual line {target_line}. Verify.")
        
        # Control whether we insert BEFORE or AFTER the row that starts at target_line
        if position not in ("before", "after"):
            raise SystemExit("position must be 'before' or 'after'.")
        if position == "after":
            insert_idx += 1
        
        updated = rows[:]
        updated[insert_idx:insert_idx] = new_rows_ordered
        out_text = join_rows_crlf(updated)

        if output_path:
            write_text(output_path, out_text)
            print(f"[INSERT] Wrote {output_path} (inserted {len(new_rows_ordered)} rows at visual line {target_line})")
        else:
            if backup:
                bak = input_path + ".bak"
                if not os.path.exists(bak):
                    write_text(bak, text)
                    print(f"[INSERT] Backup written: {bak}")
            write_text(input_path, out_text)
            print(f"[INSERT] Updated in-place: {input_path} at visual line {target_line}")
        return

    raise SystemExit(f"Unknown mode: {mode_to_do}")


def main():
    ap = argparse.ArgumentParser(description="Add/Update CSV rows by key range, preserving CRLF rows and LF inside cells.")
    ap.add_argument("--input", required=True, help="Path to target texts.csv")
    ap.add_argument("--output", default=None, help="Optional output path; if omitted, edits input in-place (with .bak)")
    ap.add_argument("--mode", choices=["update","insert","auto"], default="auto",
                    help="update: replace existing block; insert: add at target line; auto: update if present+contiguous, else insert")
    ap.add_argument("--start-key", required=True, help="First key (inclusive), e.g., KYHF or WU10")
    ap.add_argument("--end-key", required=True, help="Last key (inclusive), e.g., 9JVP or WU23")
    ap.add_argument("--target-line", type=int, default=None, help="Line (including LF and CRLF breaks) to insert at (or to validate in update)")
    ap.add_argument("--position", choices=["before","after"], default="after",
                    help="In INSERT mode, place block before/after the row that starts at --target-line (default: after)")
    ap.add_argument("--no-validate-line", action="store_true", help="Do not validate target-line in update mode")
    ap.add_argument("--no-backup", action="store_true", help="Do not write .bak when overwriting input")
    args = ap.parse_args()

    run(
        input_path=args.input,
        output_path=args.output,
        mode=args.mode,
        start_key=args.start_key,
        end_key=args.end_key,
        target_line=args.target_line,
        position=args.position,
        validate_line=not args.no_validate_line,
        backup=not args.no_backup,
    )


if __name__ == "__main__":
    # RUN AS: python patch_texts.py --input texts.csv --mode insert --start-key WU10 --end-key WU23 --target-line 2445
    main()
