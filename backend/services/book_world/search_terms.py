"""Deterministic Chinese character terms, shared by FTS writes and scoped queries."""

import re
import sqlite3
import unicodedata


def terms(text: str, *, single_characters: bool = True) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    result: set[str] = set(re.findall(r"[a-z0-9]+", text))
    for fragment in re.findall(r"[\u3400-\u9fff]+", text):
        if single_characters or len(fragment) == 1:
            result.update(fragment)
        for size in (2, 3):
            result.update(
                fragment[index : index + size] for index in range(len(fragment) - size + 1)
            )
    return sorted(result, key=lambda value: (-len(value), value))


def register_search_functions(db: sqlite3.Connection) -> None:
    db.create_function(
        "book_search_terms", 1, lambda value: " ".join(terms(value or "")), deterministic=True
    )


def query_terms(query: str, aliases: list[str]) -> list[str]:
    query = unicodedata.normalize("NFKC", query).casefold()
    for alias in sorted(aliases, key=len, reverse=True):
        query = query.replace(unicodedata.normalize("NFKC", alias).casefold(), " ")
    for phrase in (
        "可以告诉我",
        "我想知道",
        "在原著中",
        "你知道",
        "你觉得",
        "你认为",
        "原著",
        "书中",
        "请问",
        "为什么",
        "在哪里",
        "怎么样",
        "怎么看",
        "有没有",
        "是什么",
        "是不是",
        "是否",
        "如何",
        "能否",
        "什么",
        "哪里",
        "是谁",
        "吗",
        "呢",
    ):
        query = query.replace(phrase, " ")
    generic = {"人物", "角色", "知道", "了解", "关于", "告诉", "事情", "看法", "觉得", "认为"}
    return [term for term in terms(query, single_characters=False) if term not in generic][:32]
