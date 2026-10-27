import re
from langchain_community.tools import WikipediaQueryRun, DuckDuckGoSearchRun
from langchain_community.utilities import WikipediaAPIWrapper, DuckDuckGoSearchAPIWrapper
from langchain_classic.tools import Tool
from datetime import datetime
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


search_wrapper = DuckDuckGoSearchAPIWrapper(region="us-en", max_results=5)


def web_search(query: str) -> str:
    """Safely execute web search with region fix and error handling."""
    if not query or not query.strip():
        return "No search query provided."
    clean_query = query.strip()
    try:
        results = search_wrapper.run(clean_query)
        if results and results.strip():
            return results
    except Exception as e:
        # Fallback: remove site: filters or specific operators if DDG encounters upstream errors
        try:
            fallback = re.sub(r'site:\S+', '', clean_query).strip()
            if fallback and fallback != clean_query:
                res = search_wrapper.run(fallback)
                if res and res.strip():
                    return res
        except Exception:
            pass
        return f"Live web search is temporarily unavailable ({str(e)}). Please synthesize your answer based on your knowledge."

    return f"No relevant web search results found for '{clean_query}'."


class _SearchRunner:
    def run(self, query: str) -> str:
        return web_search(query)


search = _SearchRunner()

search_tool = Tool(
    name="search",
    func=web_search,
    description="Search the web for up-to-date information, documentation, and facts.",
)

api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=100)
wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

retail_ddg = DuckDuckGoSearchAPIWrapper(region="in-en")


RETAIL_SITES = [
    ("amazon.in", "Amazon"),
    ("flipkart.com", "Flipkart"),
    ("reliancedigital.in", "Reliance Digital"),
    ("croma.com", "Croma"),
    ("tatacliq.com", "Tata CLiQ"),
    ("myntra.com", "Myntra"),
    ("ajio.com", "AJIO"),
    ("nykaa.com", "Nykaa"),
    ("paytmmall.com", "Paytm Mall"),
    ("shopclues.com", "ShopClues"),
    ("snapdeal.com", "Snapdeal"),
    ("jiomart.com", "JioMart"),
]

# URL path patterns that indicate a direct product page (not a category/search page)
_PRODUCT_PATH_PATTERNS = [
    "/dp/", "/gp/product/", "/product/", "/p/",
    "/itm/", "/prd", "/sku/", "/pd/",
]


def _is_product_url(url: str) -> bool:
    path = url.split("?", 1)[0].lower()
    return any(p in path for p in _PRODUCT_PATH_PATTERNS)


def _title_matches(query: str, title: str) -> bool:
    """Check if the search query appears meaningfully in the title."""
    q_words = set(query.lower().split())
    t_lower = title.lower()
    # At least 2 significant words from the query should appear in the title
    # Filter out common words that are too generic
    stopwords = {"buy", "online", "price", "india", "for", "the", "a", "an", "in", "of", "to", "and", "with", "at"}
    significant = [w for w in q_words if w not in stopwords and len(w) > 1]
    if not significant:
        return True
    matches = sum(1 for w in significant if w in t_lower)
    return matches >= max(1, len(significant) - 1)


def _detect_store(url: str, title: str = "", snippet: str = "") -> str:
    combined = (url + " " + title + " " + snippet).lower()
    for domain, name in RETAIL_SITES:
        if domain in combined:
            return name
    return ""


def search_products(product_query: str) -> list[dict]:
    """Search for a product across Indian retail sites.

    Returns scored, deduplicated list with keys: title, snippet, price, store, url.
    """
    all_results = []

    # Step 1 — site-specific queries (primary, reliable source)
    for domain, name in RETAIL_SITES:
        try:
            results = retail_ddg.results(f"site:{domain} {product_query}", max_results=5)
            for r in results:
                url = r.get("link", "")
                if not url:
                    continue
                all_results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": url,
                    "store": name,
                    "_source": "site",
                })
        except Exception:
            continue

    # Step 2 — general query as fallback when site-specific results are thin
    product_count = len({r["url"] for r in all_results})
    if product_count < 12:
        try:
            results = retail_ddg.results(
                f"{product_query} price india buy online", max_results=10
            )
            for r in results:
                url = r.get("link", "")
                if not url or any(u["url"] == url for u in all_results):
                    continue
                store = _detect_store(url, r.get("title", ""), r.get("snippet", ""))
                if store or _is_product_url(url):
                    all_results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                        "url": url,
                        "store": store,
                        "_source": "general",
                    })
        except Exception:
            pass

    # Step 3 — deduplicate, score, sort
    seen_urls = set()
    scored = []
    for r in all_results:
        if r["url"] in seen_urls:
            continue
        seen_urls.add(r["url"])

        text = r["title"] + " " + r["snippet"]
        price_match = re.search(r'₹\s?[\d,]+(?:\.\d{2})?', text)
        price = price_match.group(0) if price_match else ""

        title_ok = _title_matches(product_query, r["title"])

        score = 0
        if _is_product_url(r["url"]):
            score += 3
        if price:
            score += 2
        if r["store"]:
            score += 1
        if r["_source"] == "site":
            score += 1
        if not title_ok:
            score -= 5  # heavily penalize unrelated results

        scored.append({
            "title": r["title"],
            "snippet": r["snippet"],
            "price": price,
            "store": r["store"],
            "url": r["url"],
            "_score": score,
        })

    scored.sort(key=lambda x: x["_score"], reverse=True)
    # Only include results with non-negative score
    scored = [r for r in scored if r["_score"] >= 0]
    for r in scored:
        del r["_score"]
    return scored[:25]


product_search_tool = Tool(
    name="product_search",
    func=lambda q: str(search_products(q)),
    description="Search Indian online retail sites (Amazon.in, Flipkart, etc.) for products and get listing details. Input should be a product name.",
)


class SaveFileInput(BaseModel):
    data: str = Field(description="The text content or research data to save.")
    filename: str = Field(default="research_output.txt", description="The target filename, e.g., 'life.txt'.")


def save_to_txt(data: str, filename: str = "research_output.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"--- Research Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"

    with open(filename, "a", encoding="utf-8") as f:
        f.write(formatted_text)

    return f"Data successfully saved to {filename}"


save_tool = StructuredTool.from_function(
    func=save_to_txt,
    name="save_text_to_file",
    description="Saves structured research data to a specific text file.",
    args_schema=SaveFileInput
)


def _search_local_context(query: str) -> str:
    """Search uploaded files, policies, and documents in the /context directory."""
    from rag_service import query_context
    result = query_context(query)
    return result.get("answer", "No answer found in context.")


context_search_tool = Tool(
    name="context_policy_search",
    func=_search_local_context,
    description="Search through uploaded user files, documents, policies, or spreadsheets in /context for facts, clauses, coverage, rates, and rules.",
)

