import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    "index": "CAR Index",
    "charts": "CAR Charts",
    "stories": "Stories",
    "what-is-car": "What CAR is and isn't",
    "about": "About JTE Sports",
}
ARTICLE_TYPE_NAMES = {"Article", "NewsArticle"}
SITE_ORIGIN = "https://jtesports.com"


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))


class SiteContractTests(unittest.TestCase):
    def test_public_routes_are_real_indexable_documents(self):
        for route, heading in ROUTES.items():
            with self.subTest(route=route):
                path = ROOT / route / "index.html"
                self.assertTrue(path.is_file(), f"missing 200-serving route: /{route}")
                html = path.read_text(encoding="utf-8")
                self.assertIn(f'<link rel="canonical" href="https://jtesports.com/{route}/">', html)
                self.assertIn(f"<h1>{heading}</h1>", html)
                self.assertNotIn('name="robots" content="noindex', html)

    def test_spa_links_have_real_href_fallbacks(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        parser = _AnchorParser()
        parser.feed(html)
        offenders = [a for a in parser.anchors if "showPage(" in a.get("onclick", "") and not a.get("href")]
        self.assertEqual([], offenders)

    def test_large_third_party_scripts_do_not_block_html_parsing(self):
        for rel in ("index.html", "writing/vitality-downfall.html"):
            html = (ROOT / rel).read_text(encoding="utf-8")
            parser = HTMLParser()
            del parser  # standard parser is only used to make this a structural test module
            for src in ("papaparse.min.js", "plotly-2.35.2.min.js"):
                if src in html:
                    tag = re.search(rf"<script[^>]+{re.escape(src)}[^>]*>", html)
                    self.assertIsNotNone(tag, f"missing script tag for {src} in {rel}")
                    self.assertIn("defer", tag.group(0), f"render-blocking {src} in {rel}")

    def test_car_dataset_is_loaded_on_demand(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("function ensureCarReady()", html)
        show_page = re.search(r"function showPage\(.*?\n  }\n", html, flags=re.DOTALL)
        self.assertIsNotNone(show_page)
        self.assertIn("ensureCarReady()", show_page.group(0))
        init_car = re.search(r"async function initCar\(\).*?\n  }\n", html, flags=re.DOTALL)
        self.assertIsNotNone(init_car)
        self.assertNotIn("await loadCarData()", init_car.group(0))

    def test_articles_expose_machine_readable_metadata_and_landmark(self):
        for path in sorted((ROOT / "writing").glob("*.html")):
            with self.subTest(article=path.name):
                html = path.read_text(encoding="utf-8")
                self.assertIn('<link rel="icon" type="image/jpeg"', html)
                self.assertIn("<main", html)
                self.assertIn("</main>", html)
                self.assertRegex(html, r'<time[^>]+datetime="\d{4}-\d{2}-\d{2}"')
                blocks = re.findall(
                    r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                    html,
                    flags=re.DOTALL,
                )
                articles = []
                for block in blocks:
                    data = json.loads(block)
                    if data.get("@type") in {"Article", "NewsArticle"}:
                        articles.append(data)
                self.assertEqual(1, len(articles), "expected exactly one Article JSON-LD block")
                article = articles[0]
                for field in ("headline", "description", "datePublished", "author", "publisher", "mainEntityOfPage"):
                    self.assertIn(field, article)

    def test_about_exposes_profile_entity_and_social_metadata(self):
        html = (ROOT / "about/index.html").read_text(encoding="utf-8")
        for tag in (
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="JTE Sports">',
            '<meta property="og:url" content="https://jtesports.com/about/">',
            '<meta property="og:title" content="About JTE Sports · Independent esports analytics">',
            '<meta property="og:description" content="JTE Sports is an independent analytics publication for professional League of Legends, combining the CAR Index with long-form reporting.">',
            '<meta property="og:image" content="https://jtesports.com/images/twitter-banner.png">',
            '<meta name="twitter:card" content="summary_large_image">',
            '<meta name="twitter:site" content="@jt_esports">',
            '<meta name="twitter:creator" content="@jt_esports">',
            '<meta name="twitter:title" content="About JTE Sports · Independent esports analytics">',
            '<meta name="twitter:description" content="JTE Sports is an independent analytics publication for professional League of Legends, combining the CAR Index with long-form reporting.">',
            '<meta name="twitter:image" content="https://jtesports.com/images/twitter-banner.png">',
        ):
            self.assertIn(tag, html)
        blocks = re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            html,
            flags=re.DOTALL,
        )
        graphs = [json.loads(block) for block in blocks]
        entities = [entity for graph in graphs for entity in graph.get("@graph", [graph])]
        profile = next(data for data in entities if data.get("@type") == "ProfilePage")
        person = next(data for data in entities if data.get("@type") == "Person")
        self.assertEqual("https://jtesports.com/about/#profile", profile.get("@id"))
        self.assertEqual("https://jtesports.com/about/", profile.get("url"))
        self.assertEqual({"@id": "https://jtesports.com/about/#jte"}, profile.get("mainEntity"))
        self.assertEqual("https://jtesports.com/about/#jte", person.get("@id"))
        self.assertEqual("JTE", person.get("name"))
        self.assertEqual("JTE is pseudonymous.", person.get("description"))
        self.assertEqual("https://jtesports.com/about/", person.get("url"))
        self.assertEqual(["https://twitter.com/jt_esports", "https://x.com/jt_esports"], person.get("sameAs"))

    def test_article_json_ld_matches_visible_page_contract(self):
        sitemap = ElementTree.parse(ROOT / "sitemap.xml")
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        article_urls = [
            url.find("s:loc", ns).text
            for url in sitemap.findall("s:url", ns)
            if "/writing/" in url.find("s:loc", ns).text
        ]
        self.assertGreater(len(article_urls), 0)
        for url in article_urls:
            with self.subTest(article=url):
                path = ROOT / url.removeprefix(f"{SITE_ORIGIN}/")
                self.assertTrue(path.is_file(), f"sitemap article is not a local document: {url}")
                html = path.read_text(encoding="utf-8")
                blocks = re.findall(
                    r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                    html,
                    flags=re.DOTALL,
                )
                articles = [json.loads(block) for block in blocks]
                articles = [data for data in articles if data.get("@type") in ARTICLE_TYPE_NAMES]
                self.assertEqual(1, len(articles), "expected exactly one Article JSON-LD block")
                article = articles[0]

                canonical = re.search(r'<link rel="canonical" href="([^"]+)">', html)
                description = re.search(r'<meta name="description" content="([^"]+)">', html)
                og_title = re.search(r'<meta property="og:title" content="([^"]+)">', html)
                og_image = re.search(r'<meta property="og:image" content="([^"]+)">', html)
                published = re.search(r'<meta property="article:published_time" content="(\d{4}-\d{2}-\d{2})">', html)
                article_author = re.search(r'<meta property="article:author" content="([^"]+)">', html)
                self.assertTrue(all((canonical, description, og_title, og_image, published)))
                twitter_title = re.search(r'<meta name="twitter:title" content="([^"]+)">', html)
                twitter_description = re.search(r'<meta name="twitter:description" content="([^"]+)">', html)
                twitter_image = re.search(r'<meta name="twitter:image" content="([^"]+)">', html)
                self.assertTrue(all((canonical, description, og_title, og_image, published, article_author, twitter_title, twitter_description, twitter_image)))
                self.assertEqual(og_title.group(1), article.get("headline"))
                self.assertEqual(description.group(1), article.get("description"))
                self.assertEqual(published.group(1), article.get("datePublished"))
                self.assertEqual("https://jtesports.com/about/", article_author.group(1))
                self.assertEqual(canonical.group(1), article.get("mainEntityOfPage"))
                self.assertEqual(og_image.group(1), article.get("image"))
                self.assertEqual(twitter_title.group(1), og_title.group(1))
                self.assertEqual(twitter_description.group(1), description.group(1))
                self.assertEqual(twitter_image.group(1), og_image.group(1))
                self.assertEqual(
                    {"@id": "https://jtesports.com/about/#jte", "@type": "Person", "name": "JTE", "url": "https://jtesports.com/about/", "sameAs": ["https://twitter.com/jt_esports", "https://x.com/jt_esports"]},
                    article.get("author"),
                )
                self.assertEqual("https://jtesports.com/#org", article.get("publisher", {}).get("@id"))
                self.assertEqual("Organization", article.get("publisher", {}).get("@type"))
                self.assertEqual("JTE Sports", article.get("publisher", {}).get("name"))
                self.assertEqual(SITE_ORIGIN + "/", article.get("publisher", {}).get("url"))
                self.assertEqual(SITE_ORIGIN + "/jte-logo.jpg", article.get("publisher", {}).get("logo"))
                self.assertEqual("en", article.get("inLanguage"))
                self.assertIs(True, article.get("isAccessibleForFree"))
                self.assertTrue(article.get("headline"))
                self.assertRegex(article["datePublished"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(article["mainEntityOfPage"].startswith(f"{SITE_ORIGIN}/"))

    def test_llms_txt_describes_the_public_site(self):
        llms = ROOT / "llms.txt"
        self.assertTrue(llms.is_file())
        text = llms.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^# JTE Sports\s*$")
        self.assertIn("https://jtesports.com/", text)
        self.assertIn("https://jtesports.com/stories/", text)
        sitemap = ElementTree.parse(ROOT / "sitemap.xml")
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url in sitemap.findall("s:url", ns):
            loc = url.find("s:loc", ns).text
            if "/writing/" in loc:
                self.assertIn(loc, text)

    def test_every_sitemap_article_is_linked_from_story_archive(self):
        sitemap = ElementTree.parse(ROOT / "sitemap.xml")
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        article_paths = {
            url.find("s:loc", ns).text.removeprefix("https://jtesports.com")
            for url in sitemap.findall("s:url", ns)
            if "/writing/" in url.find("s:loc", ns).text
        }
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        missing = sorted(path for path in article_paths if f'href="{path}"' not in home)
        self.assertEqual([], missing)

    def test_deployment_excludes_test_and_source_directories(self):
        config = (ROOT / "_config.yml").read_text(encoding="utf-8")
        for name in ("tests", "engine", "data", "deploy", "notes", "tools", "preview", "docs"):
            self.assertRegex(config, rf"(?m)^\s*-\s+{re.escape(name)}\s*$")


if __name__ == "__main__":
    unittest.main()
