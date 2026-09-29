"""结果视图过滤契约；不参与抓取、训练、AI 或通知。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


RULE_KINDS = frozenset({"keyword", "word", "regex_alias"})
MAX_PATTERN = 128
MAX_RULES = 50
MAX_PREVIEW = 100


class InvalidRule(ValueError):
    pass


class ResultViewHttpError(HTTPException):
    """由 Web 入口输出稳定的扁平错误体。"""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def _aliases(pattern: str) -> tuple[list[str], bool, bool]:
    """安全别名语法：可选首尾锚点和 1–8 个纯字面量分支。"""
    anchored_start = pattern.startswith("^")
    anchored_end = pattern.endswith("$")
    body = pattern[int(anchored_start):len(pattern) - int(anchored_end) or None]
    values = body.split("|")
    forbidden = set("\\[](){}*+?.^$")
    if (not 1 <= len(values) <= 8 or any(
        not value.strip() or len(value) > 64 or value != value.strip()
        or any(char in forbidden or ord(char) < 32 for char in value)
        for value in values
    )):
        raise InvalidRule("正则别名只支持 1–8 个用 | 分隔的字面词，可选首尾 ^ 和 $ 锚点。")
    return values, anchored_start, anchored_end


def validate_rule(kind: str, pattern: str) -> None:
    if kind not in RULE_KINDS or not isinstance(pattern, str) or not 1 <= len(pattern) <= MAX_PATTERN:
        raise InvalidRule("规则类型或长度无效。")
    if not pattern.strip() or pattern != pattern.strip() or any(ord(char) < 32 for char in pattern):
        raise InvalidRule("规则不能包含空白边缘或控制字符。")
    if kind == "regex_alias":
        _aliases(pattern)


def _texts(record: dict) -> list[str]:
    product = record.get("商品信息") or {}
    seller = record.get("卖家信息") or {}
    return [str(product.get("商品标题") or "")[:2048],
            str(product.get("商品描述") or "")[:2048],
            str(seller.get("卖家昵称") or product.get("卖家昵称") or "")[:512]]


def _word_match(text: str, needle: str) -> bool:
    start = 0
    while (at := text.find(needle, start)) >= 0:
        end = at + len(needle)
        left_ok = at == 0 or not text[at - 1].isascii() or not text[at - 1].isalnum()
        right_ok = end == len(text) or not text[end].isascii() or not text[end].isalnum()
        if left_ok and right_ok:
            return True
        start = at + 1
    return False


def rule_matches(record: dict, rule: dict, task_ref: str | None) -> bool:
    if not rule.get("enabled") or (rule.get("scope") == "task" and rule.get("task_ref") != task_ref):
        return False
    kind, pattern = rule["kind"], rule["pattern"]
    validate_rule(kind, pattern)
    values, start, end = _aliases(pattern) if kind == "regex_alias" else ([pattern], False, False)
    for raw in _texts(record):
        text = raw.casefold()
        for value in values:
            needle = value.casefold()
            if kind == "word":
                if _word_match(text, needle):
                    return True
            elif start and end:
                if text == needle:
                    return True
            elif start:
                if text.startswith(needle):
                    return True
            elif end:
                if text.endswith(needle):
                    return True
            elif needle in text:
                return True
    return False


def apply_view_rules(records: list[dict], hidden_ids: set[str], rules: list[dict],
                     item_id_of, task_ref_of, *, include_hidden: bool = False) -> tuple[list[dict], dict[str, int]]:
    """在分页前统一计算可见列表和视图统计。"""
    visible: list[dict] = []
    hidden_count = 0
    blacklist_count = 0
    for record in records:
        item_id = item_id_of(record)
        is_hidden = bool(item_id and item_id in hidden_ids)
        matches = [rule for rule in rules if rule_matches(record, rule, task_ref_of(record))]
        if is_hidden:
            hidden_count += 1
        if matches:
            blacklist_count += 1
        if not include_hidden and (is_hidden or matches):
            continue
        result = dict(record)
        result["view_hidden"] = is_hidden
        result["blacklist_reasons"] = [{"rule_id": rule["id"], "kind": rule["kind"],
                                         "pattern": rule["pattern"]} for rule in matches]
        visible.append(result)
    return visible, {"total_items": len(visible), "hidden_count": hidden_count,
                     "blacklist_count": blacklist_count}
