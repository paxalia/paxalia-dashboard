"""Bot classification and transparent, UA-derived crawler identity labels.

Path rules are authoritative for scanner traffic. User-Agent classification is
informational and is explicitly not an IP-ownership verification mechanism.
"""
from __future__ import annotations

import re

_SEARCH_ENGINE_IDENTITIES = [
    ("Googlebot", "Google", r"Googlebot"),
    ("Google Inspection Tool", "Google", r"Google-InspectionTool"),
    ("Google AdsBot", "Google", r"AdsBot-Google"),
    ("Google Mediabot", "Google", r"Mediapartners-Google"),
    ("Bingbot", "Microsoft Bing", r"Bingbot"),
    ("Bing Preview", "Microsoft Bing", r"BingPreview"),
    ("Yahoo Slurp", "Yahoo", r"Slurp"),
    ("DuckDuckBot", "DuckDuckGo", r"DuckDuckBot"),
    ("Baiduspider", "Baidu", r"Baiduspider"),
    ("YandexBot", "Yandex", r"YandexBot"),
    ("Yandex Images", "Yandex", r"YandexImages"),
    ("Sogou", "Sogou", r"Sogou"),
    ("Exabot", "Exalead", r"Exabot"),
    ("Applebot", "Apple", r"Applebot"),
    ("PetalBot", "Huawei", r"PetalBot"),
    ("SeznamBot", "Seznam", r"SeznamBot"),
]

_AI_IDENTITIES = [
    ("GPTBot", "OpenAI", r"GPTBot"),
    ("ChatGPT-User", "OpenAI", r"ChatGPT-User"),
    ("OAI-SearchBot", "OpenAI", r"OAI-SearchBot"),
    ("ClaudeBot", "Anthropic", r"ClaudeBot"),
    ("Claude Web", "Anthropic", r"Claude-Web"),
    ("Anthropic crawler", "Anthropic", r"anthropic-ai"),
    ("CCBot", "Common Crawl", r"CCBot"),
    ("Bytespider", "ByteDance", r"Bytespider"),
    ("Amazonbot", "Amazon", r"Amazonbot"),
    ("PerplexityBot", "Perplexity", r"PerplexityBot"),
    ("Google-Extended", "Google", r"Google-Extended"),
    ("Applebot-Extended", "Apple", r"Applebot-Extended"),
]

_SOCIAL_IDENTITIES = [
    ("Facebook crawler", "Meta", r"facebookexternalhit|Facebot"),
    ("Twitter/X crawler", "X", r"Twitterbot"),
    ("LinkedIn crawler", "LinkedIn", r"LinkedInBot"),
    ("Slackbot", "Slack", r"Slackbot"),
    ("Discordbot", "Discord", r"Discordbot"),
    ("WhatsApp crawler", "Meta", r"WhatsApp"),
    ("TelegramBot", "Telegram", r"TelegramBot"),
    ("Skype preview", "Microsoft", r"SkypeUriPreview"),
    ("Redditbot", "Reddit", r"redditbot"),
]

_SEO_IDENTITIES = [
    ("AhrefsBot", "Ahrefs", r"AhrefsBot"),
    ("SemrushBot", "Semrush", r"SemrushBot"),
    ("MJ12bot", "Majestic", r"MJ12bot"),
    ("DotBot", "Moz", r"DotBot"),
    ("BLEXBot", "BLEX", r"BLEXBot"),
    ("DataForSeoBot", "DataForSEO", r"DataForSeoBot"),
]

_CATEGORY_PATTERNS = [
    ("search_engine", _SEARCH_ENGINE_IDENTITIES),
    ("ai_crawler", _AI_IDENTITIES),
    ("social_preview", _SOCIAL_IDENTITIES),
    ("seo_tool", _SEO_IDENTITIES),
]

_COMPILED_CATEGORY_PATTERNS = [
    (category, [(name, provider, re.compile(pattern, re.IGNORECASE)) for name, provider, pattern in entries])
    for category, entries in _CATEGORY_PATTERNS
]

_GENERIC_BOT_HEURISTIC = re.compile(
    r"bot|crawler|spider|scrapy|slurp|curl/|wget/|python-requests|"
    r"go-http-client|libwww-perl|okhttp|java/|axios/",
    re.IGNORECASE,
)


def classify_bot_identity(is_malicious_path: bool, user_agent: str) -> dict:
    """Return a transparent classification/identity record.

    ``confidence`` is intentionally about the evidence source, not a claim
    that the client has been authenticated. UA-derived identities are ``claimed``;
    configured path rules are ``rule`` evidence.
    """
    if is_malicious_path:
        return {
            "category": "malicious",
            "name": "Configured scanner path",
            "provider": "Paxalia path rule",
            "confidence": "rule",
        }

    ua = (user_agent or "").strip()
    if not ua:
        return {
            "category": "unknown",
            "name": "Unknown automated client",
            "provider": "Unknown",
            "confidence": "heuristic",
        }

    for category, entries in _COMPILED_CATEGORY_PATTERNS:
        for name, provider, pattern in entries:
            if pattern.search(ua):
                return {
                    "category": category,
                    "name": name,
                    "provider": provider,
                    "confidence": "claimed",
                }

    if _GENERIC_BOT_HEURISTIC.search(ua):
        return {
            "category": "unknown",
            "name": "Generic bot-like client",
            "provider": "Unknown",
            "confidence": "heuristic",
        }

    return {
        "category": "",
        "name": "Not classified as a bot",
        "provider": "",
        "confidence": "none",
    }


def classify_bot(is_malicious_path, user_agent):
    """Return the historical bot-category string used by PageView."""
    return classify_bot_identity(bool(is_malicious_path), user_agent).get("category", "")
