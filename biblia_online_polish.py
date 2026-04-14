import argparse
import json
import os
import re
import time
from html import unescape

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://biblia-online.pl"
REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 0.15
REQUEST_RETRY_COUNT = 4
REQUEST_RETRY_BACKOFF_SECONDS = 1.5

# Canonical order used by existing repository outputs.
BOOKS_ENGLISH = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel",
    "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalm", "Proverbs", "Ecclesiastes", "Song Of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
    "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

TRANSLATION_PRESETS = {
    "BT": "Tysiaclecia",
    "BW": "Warszawska",
    "BG1632": "Gdanska",
    "BG1881": "BibliaGdanska1881",
    "WUJ": "JakubaWujka",
    "NBG": "NowaBibliaGdanska",
    "PT": "PrzekladTorunski",
    "UBG": "UwspolczesnionaBibliaGdanska",
}

VERSE_BLOCK_RE = re.compile(
    r'<div id="vt\d+"[^>]*\sn="(?P<verse>\d+)"[^>]*>(?P<text>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
NEXT_CHAPTER_RE = re.compile(
    r'/Biblia/(?P<translation>[^/]+)/(?P<slug>[^/]+)/(?P<chapter>\d+)/1',
    re.IGNORECASE,
)

TYSIACLECIA_NON_CANONICAL_SLUGS = {
    "Ksiega-Tobiasza",
    "Ksiega-Judyty",
    "1-Ksiega-Machabejska",
    "2-Ksiega-Machabejska",
    "Ksiega-Madrosci",
    "Madrosc-Syracha",
    "Ksiega-Barucha",
}


def clean_html_text(raw_html):
    no_tags = re.sub(r"<[^>]+>", " ", raw_html)
    collapsed = re.sub(r"\s+", " ", unescape(no_tags)).strip()
    return collapsed


def http_get(session, url, retries=REQUEST_RETRY_COUNT, retry_backoff_seconds=REQUEST_RETRY_BACKOFF_SECONDS):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == retries:
                break

            wait_seconds = retry_backoff_seconds * attempt
            print(
                f"\n[+] Request failed ({attempt}/{retries}) for {url}: {exc}. "
                f"Retrying in {wait_seconds:.1f}s..."
            )
            time.sleep(wait_seconds)

    raise last_error


def filter_to_canonical_slugs(slugs, translation_slug):
    if len(slugs) <= 66:
        return slugs

    if translation_slug == "Tysiaclecia":
        canonical = [slug for slug in slugs if slug not in TYSIACLECIA_NON_CANONICAL_SLUGS]
        if len(canonical) == 66:
            return canonical

    return slugs


def fetch_translation_books(session, translation_slug):
    url = f"{BASE_URL}/Biblia/{translation_slug}/1-Ksiega-Mojzeszowa/1/1"
    html = http_get(session, url)
    soup = BeautifulSoup(html, "html.parser")

    options = []
    for opt in soup.select("option.rnav-book-opt"):
        value_raw = opt.get("value", "").strip()
        slug = (opt.get("n", "") or "").strip()
        label = clean_html_text(opt.get_text(" ", strip=True))

        if not value_raw.isdigit():
            continue
        value = int(value_raw)
        if 1 <= value <= 66 and slug:
            options.append((value, slug, label))

    dedup = {}
    for value, slug, label in options:
        if value not in dedup:
            dedup[value] = (slug, label)

    # Some translations (e.g. UBG) do not expose a complete numeric option list.
    # Fall back to the explicit book links from ListaKsiag.
    if len(dedup) < 66:
        list_url = f"{BASE_URL}/Biblia/ListaKsiag/{translation_slug}/"
        list_html = http_get(session, list_url)
        list_soup = BeautifulSoup(list_html, "html.parser")

        link_re = re.compile(rf"^/Biblia/{re.escape(translation_slug)}/([^/]+)/1/1$")
        slugs = []
        for a in list_soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            match = link_re.match(href)
            if not match:
                continue
            book_slug = match.group(1)
            if book_slug not in slugs:
                slugs.append(book_slug)

        slugs = filter_to_canonical_slugs(slugs, translation_slug)

        if len(slugs) >= 66:
            ordered = []
            for idx in range(66):
                ordered.append({
                    "index": idx + 1,
                    "slug": slugs[idx],
                    "label": slugs[idx],
                    "english": BOOKS_ENGLISH[idx],
                })
            return ordered

    ordered = []
    for idx in range(1, 67):
        if idx not in dedup:
            raise RuntimeError(f"Could not find book option {idx} for translation '{translation_slug}'.")
        slug, label = dedup[idx]
        ordered.append({
            "index": idx,
            "slug": slug,
            "label": label,
            "english": BOOKS_ENGLISH[idx - 1],
        })

    return ordered


def parse_chapter_verses(html):
    verses = {}
    for match in VERSE_BLOCK_RE.finditer(html):
        verse_number = match.group("verse")
        verse_text = clean_html_text(match.group("text"))
        if verse_text:
            verses[verse_number] = verse_text
    return verses


def extract_next_chapter_info(html):
    soup = BeautifulSoup(html, "html.parser")

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        title = clean_html_text(anchor.get("title", ""))

        if "następny rozdział" not in title.lower():
            continue

        match = NEXT_CHAPTER_RE.search(href)
        if not match:
            continue

        return {
            "href": href,
            "translation": match.group("translation"),
            "slug": match.group("slug"),
            "chapter": int(match.group("chapter")),
        }

    return None


def download_book(session, translation_slug, book_meta, sleep_seconds=REQUEST_DELAY_SECONDS):
    book_slug = book_meta["slug"]
    chapter = 1
    chapters = {}

    while True:
        chapter_url = f"{BASE_URL}/Biblia/{translation_slug}/{book_slug}/{chapter}/1"
        html = http_get(session, chapter_url)
        verses = parse_chapter_verses(html)

        if not verses:
            break

        chapters[str(chapter)] = verses

        next_info = extract_next_chapter_info(html)
        if not next_info:
            break

        # Stop when next chapter moves into a different book.
        if next_info["slug"] != book_slug:
            break

        expected_next = chapter + 1
        if next_info["chapter"] != expected_next:
            break

        chapter = expected_next
        time.sleep(sleep_seconds)

    return {book_meta["english"]: chapters}


def combine_books(books_folder, output_file, translation_code, translation_slug):
    combined_data = {}
    for file_name in os.listdir(books_folder):
        if not file_name.endswith(".json"):
            continue
        file_path = os.path.join(books_folder, file_name)
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            combined_data.update(data)

    formatted = {
        "translation": f"{translation_code}: biblia-online.pl/{translation_slug}",
        "books": [],
    }

    for book in BOOKS_ENGLISH:
        if book not in combined_data:
            continue

        chapter_map = combined_data[book]
        chapter_list = []
        for chapter_key in sorted(chapter_map.keys(), key=lambda x: int(x)):
            verses = chapter_map[chapter_key]
            verse_list = []
            for verse_key in sorted(verses.keys(), key=lambda x: int(x)):
                verse_list.append({
                    "verse": int(verse_key),
                    "text": verses[verse_key],
                })

            chapter_list.append({
                "chapter": int(chapter_key),
                "verses": verse_list,
            })

        formatted["books"].append({
            "name": book,
            "chapters": chapter_list,
        })

    with open(output_file, "w", encoding="utf-8") as out_file:
        json.dump(formatted, out_file, indent=4, ensure_ascii=False)


def generate_progress_bar(progress, total, length=30):
    ratio = min(progress / total, 1)
    done = int(ratio * length)
    return f"[{'#' * done}{'-' * (length - done)}] {progress:2d}/{total}"


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)


def ensure_clean_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)
        return 0

    removed = 0
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
            removed += 1
    return removed


def load_existing_book(file_path, expected_book_name):
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    chapters = data.get(expected_book_name)
    if not isinstance(chapters, dict) or not chapters:
        return None

    for verses in chapters.values():
        if isinstance(verses, dict) and verses:
            return data

    return None


def resolve_translation_slug(args):
    if args.translation_slug:
        return args.translation_code.upper(), args.translation_slug

    code = args.translation_code.upper()
    if code not in TRANSLATION_PRESETS:
        available = ", ".join(sorted(TRANSLATION_PRESETS.keys()))
        raise SystemExit(
            f"Unknown translation code '{code}'. Use one of: {available}, or pass --translation-slug directly."
        )

    return code, TRANSLATION_PRESETS[code]


def main():
    parser = argparse.ArgumentParser(
        description="Download Polish Bible translations from biblia-online.pl into this repository JSON format."
    )
    parser.add_argument("--translation-code", default="BW", help="Local output code, e.g. BW, WUJ, UBG")
    parser.add_argument(
        "--translation-slug",
        default=None,
        help="biblia-online slug, e.g. Warszawska, JakubaWujka, UwspolczesnionaBibliaGdanska",
    )
    parser.add_argument(
        "--max-books",
        type=int,
        default=0,
        help="Optional limit for testing (0 means all books).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=REQUEST_DELAY_SECONDS,
        help="Delay between chapter requests in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=REQUEST_RETRY_COUNT,
        help="Retry count for failed HTTP requests.",
    )
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        help="Resume from existing book JSON files when present (default).",
    )
    resume_group.add_argument(
        "--fresh",
        dest="resume",
        action="store_false",
        help="Delete existing book JSON files before downloading.",
    )
    parser.set_defaults(resume=True)
    args = parser.parse_args()

    translation_code, translation_slug = resolve_translation_slug(args)

    root_folder = translation_code
    books_folder = os.path.join(root_folder, f"{translation_code}_books")
    output_file = os.path.join(root_folder, f"{translation_code}_bible.json")

    ensure_folder(root_folder)
    ensure_folder(books_folder)

    if args.resume:
        existing_count = len([name for name in os.listdir(books_folder) if name.endswith(".json")])
        print(f"[+] Resume mode: keeping {existing_count} existing file(s) in {books_folder}")
    else:
        deleted_count = ensure_clean_folder(books_folder)
        print(f"[+] Cleared {deleted_count} file(s) from {books_folder}")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "BibleTranslationsBot/1.0 (+https://github.com/jadenzaleski/bible-translations; "
                "educational personal use)"
            )
        }
    )

    print(f"[+] Loading books for translation slug: {translation_slug}")
    books_meta = fetch_translation_books(session, translation_slug)

    if args.max_books > 0:
        books_meta = books_meta[: args.max_books]

    total = len(books_meta)
    failed_books = []
    for idx, book_meta in enumerate(books_meta, start=1):
        output_path = os.path.join(books_folder, f"{book_meta['english']}.json")
        if args.resume and load_existing_book(output_path, book_meta["english"]) is not None:
            print(
                f"\r[+] Downloading {translation_code:<8} "
                f"{generate_progress_bar(idx, total)} {book_meta['english'][:18]:<18} cached",
                end="",
            )
            continue

        try:
            data = download_book(session, translation_slug, book_meta, sleep_seconds=args.delay)
        except requests.RequestException as exc:
            failed_books.append(book_meta["english"])
            print(
                f"\n[+] Warning: failed while downloading {book_meta['english']} "
                f"({book_meta['slug']}): {exc}"
            )
            continue

        if not data[book_meta["english"]]:
            print(f"\n[+] Warning: no chapters found for {book_meta['english']} ({book_meta['slug']}).")
            failed_books.append(book_meta["english"])
            continue

        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

        print(
            f"\r[+] Downloading {translation_code:<8} "
            f"{generate_progress_bar(idx, total)} {book_meta['english'][:18]:<18}",
            end="",
        )

    print("\n[+] Download complete.")
    combine_books(books_folder, output_file, translation_code, translation_slug)
    print(f"[+] Combined output written to {output_file}")
    if failed_books:
        print(f"[+] Incomplete books ({len(failed_books)}): {', '.join(failed_books)}")
        print("[+] Re-run with --resume to continue from the books already saved.")


if __name__ == "__main__":
    main()
