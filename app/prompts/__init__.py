"""Prompts cho các thao tác LLM - RAG v2 Pipeline."""

from app.prompts.parse_intent import PARSE_INTENT_PROMPT
from app.prompts.generate_menu import GENERATE_MENU_PROMPT
from app.prompts.adjust_menu_from_rag import ADJUST_MENU_FROM_RAG_PROMPT
from app.prompts.combination_rules import COMBINATION_RULES_PROMPT

__all__ = [
    "PARSE_INTENT_PROMPT",
    "GENERATE_MENU_PROMPT",
    "ADJUST_MENU_FROM_RAG_PROMPT",
    "COMBINATION_RULES_PROMPT",
]

