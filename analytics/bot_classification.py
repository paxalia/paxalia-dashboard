# analytics/bot_classification.py
"""
Bot classification — separates the single, undifferentiated `is_bot`
bucket into a `bot_category`, and (deliberately, see BREAKING CHANGE
note below) widens what `is_bot` catches in the first place.

BEFORE this module: `is_bot` was set purely from a path match against
AnalyticsSettings.bot_paths — a list of known scanner/attack-probe
paths (`/wp-admin/install.php`, `/.env`, `/.git/config`, ...). That
means a real search-engine or AI crawler visiting an ordinary page
(e.g. Googlebot fetching `/`) was NOT flagged as a bot at all — it
silently counted as regular human traffic in Overview, Traffic,
Cohorts, Funnels, Goals, and every other view that filters on
`is_bot=False`.

THIS MODULE additionally classifies by User-Agent against a small,
maintained pattern list (search engines, AI crawlers, social-preview
bots, SEO tools) and layers that on top of the existing path check.

  ── BREAKING CHANGE ──
  `is_bot` now also becomes True for recognized crawler/tool traffic
  that previously fell through as "human". Any project with real
  search-engine or social-preview-bot traffic (i.e. almost any public
  site) will see its "human" page-view counts drop and its Bot
  Traffic counts rise after upgrading and backfilling — this is a
  correctness fix (that traffic was never really human), not a
  regression, but it changes numbers on dashboards people are used to
  reading, so it's called out here exactly as prominently as the
  Phase 4 permissions change. Existing rows are NOT reclassified
  automatically — run `manage.py backfill_pageview_bot_category` to
  apply this to history; see that command for why it's a deliberate,
  explicit step rather than a migration data-op.

CAVEAT (spoofing): User-Agent is exactly what the request claims to
be — nothing here verifies it (that would mean a reverse-DNS lookup
against the claimed crawler's published IP ranges, which needs a
network call this package doesn't make). A malicious scanner sending
"Googlebot" as its User-Agent while probing `/wp-admin/install.php`
gets classified 'malicious', not 'search_engine' — a path match on a
known attack-probe path always wins over a UA claim, for exactly this
reason. A scanner spoofing "Googlebot" while requesting ordinary pages
will be misclassified as 'search_engine'; there's no way to catch that
without the network call this package deliberately doesn't make.

CATEGORIES (PageView.bot_category):
    ''               not a bot
    'search_engine'  Googlebot, Bingbot, DuckDuckBot, Baiduspider, ...
    'ai_crawler'     GPTBot, ClaudeBot, CCBot, PerplexityBot, ...
    'social_preview' facebookexternalhit, Twitterbot, Slackbot, ...
    'seo_tool'       AhrefsBot, SemrushBot, MJ12bot, ...
    'unknown'        looks bot-like (generic heuristic) but unmatched
    'malicious'      hit a path in AnalyticsSettings.bot_paths

Add a new entry by appending to the relevant list below — order
within a category doesn't matter, but category order in
_CATEGORY_PATTERNS does: it's evaluated top to bottom and the first
match wins, so a UA matching two lists (shouldn't happen in practice)
takes the earlier one.
"""
import re

# Real search engines and general-purpose web crawlers.
_SEARCH_ENGINE_PATTERNS = [
    r'Googlebot', r'Google-InspectionTool', r'AdsBot-Google', r'Mediapartners-Google',
    r'Bingbot', r'BingPreview',
    r'Slurp',           # Yahoo
    r'DuckDuckBot',
    r'Baiduspider',
    r'YandexBot', r'YandexImages',
    r'Sogou',
    r'Exabot',
    r'Applebot',
    r'PetalBot',        # Huawei search
    r'SeznamBot',
]

# Crawlers that identify themselves as collecting data for AI
# training or AI-answer products, distinct from traditional search
# indexing — a category people increasingly want visibility into.
_AI_CRAWLER_PATTERNS = [
    r'GPTBot', r'ChatGPT-User', r'OAI-SearchBot',
    r'ClaudeBot', r'Claude-Web', r'anthropic-ai',
    r'CCBot',           # Common Crawl
    r'Bytespider',      # TikTok / ByteDance
    r'Amazonbot',
    r'PerplexityBot',
    r'Google-Extended', r'Applebot-Extended',
]

# Link-preview / "unfurl" bots triggered when a URL is shared in a
# chat app or social platform — one-off fetches, not crawling.
_SOCIAL_PREVIEW_PATTERNS = [
    r'facebookexternalhit', r'Facebot',
    r'Twitterbot',
    r'LinkedInBot',
    r'Slackbot',
    r'Discordbot',
    r'WhatsApp',
    r'TelegramBot',
    r'SkypeUriPreview',
    r'redditbot',
]

# Commercial SEO/backlink crawlers — legitimate businesses, but many
# site owners specifically want to see this traffic broken out since
# it's neither a search engine nor a real visitor.
_SEO_TOOL_PATTERNS = [
    r'AhrefsBot',
    r'SemrushBot',
    r'MJ12bot',
    r'DotBot',
    r'BLEXBot',
    r'DataForSeoBot',
]

_CATEGORY_PATTERNS = [
    ('search_engine', _SEARCH_ENGINE_PATTERNS),
    ('ai_crawler', _AI_CRAWLER_PATTERNS),
    ('social_preview', _SOCIAL_PREVIEW_PATTERNS),
    ('seo_tool', _SEO_TOOL_PATTERNS),
]

_COMPILED_CATEGORY_PATTERNS = [
    (category, re.compile('|'.join(patterns), re.IGNORECASE))
    for category, patterns in _CATEGORY_PATTERNS
]

# Generic fallback: UA looks automated (a common bot/crawler/scraper
# token, a bare HTTP client library, or no UA at all) but doesn't match
# any maintained list above. Deliberately broad, deliberately last —
# this is what catches the long tail without needing an entry per bot.
_GENERIC_BOT_HEURISTIC = re.compile(
    r'bot|crawler|spider|scrapy|slurp|curl/|wget/|python-requests|'
    r'go-http-client|libwww-perl|okhttp|java/|axios/',
    re.IGNORECASE,
)


def classify_bot(is_malicious_path, user_agent):
    """
    Return one of the category strings documented in this module's
    docstring (never None — '' means "not a bot").

    `is_malicious_path` is the existing path-based check (kept exactly
    as-is, computed by the caller from AnalyticsSettings.bot_paths) and
    always wins, per the spoofing caveat above.
    """
    if is_malicious_path:
        return 'malicious'

    ua = user_agent or ''
    if not ua.strip():
        return 'unknown'

    for category, pattern in _COMPILED_CATEGORY_PATTERNS:
        if pattern.search(ua):
            return category

    if _GENERIC_BOT_HEURISTIC.search(ua):
        return 'unknown'

    return ''
