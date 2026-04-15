import argparse
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

GRAPHQL_URL = "https://presentation.youversionapi.com/graphql"
BEBLIA_RAW_BASE = "https://raw.githubusercontent.com/Beblia/Holy-Bible-XML-Format/master"

REQUEST_TIMEOUT = 30
REQUEST_RETRY_COUNT = 4
REQUEST_RETRY_BACKOFF_SECONDS = 1.5
DEFAULT_REQUEST_DELAY_SECONDS = 0.1

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel",
    "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalm", "Proverbs", "Ecclesiastes", "Song Of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
    "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation",
]

USFM_BOOK_CODES = {
    "Genesis": "GEN",
    "Exodus": "EXO",
    "Leviticus": "LEV",
    "Numbers": "NUM",
    "Deuteronomy": "DEU",
    "Joshua": "JOS",
    "Judges": "JDG",
    "Ruth": "RUT",
    "1 Samuel": "1SA",
    "2 Samuel": "2SA",
    "1 Kings": "1KI",
    "2 Kings": "2KI",
    "1 Chronicles": "1CH",
    "2 Chronicles": "2CH",
    "Ezra": "EZR",
    "Nehemiah": "NEH",
    "Esther": "EST",
    "Job": "JOB",
    "Psalm": "PSA",
    "Proverbs": "PRO",
    "Ecclesiastes": "ECC",
    "Song Of Solomon": "SNG",
    "Isaiah": "ISA",
    "Jeremiah": "JER",
    "Lamentations": "LAM",
    "Ezekiel": "EZK",
    "Daniel": "DAN",
    "Hosea": "HOS",
    "Joel": "JOL",
    "Amos": "AMO",
    "Obadiah": "OBA",
    "Jonah": "JON",
    "Micah": "MIC",
    "Nahum": "NAM",
    "Habakkuk": "HAB",
    "Zephaniah": "ZEP",
    "Haggai": "HAG",
    "Zechariah": "ZEC",
    "Malachi": "MAL",
    "Matthew": "MAT",
    "Mark": "MRK",
    "Luke": "LUK",
    "John": "JHN",
    "Acts": "ACT",
    "Romans": "ROM",
    "1 Corinthians": "1CO",
    "2 Corinthians": "2CO",
    "Galatians": "GAL",
    "Ephesians": "EPH",
    "Philippians": "PHP",
    "Colossians": "COL",
    "1 Thessalonians": "1TH",
    "2 Thessalonians": "2TH",
    "1 Timothy": "1TI",
    "2 Timothy": "2TI",
    "Titus": "TIT",
    "Philemon": "PHM",
    "Hebrews": "HEB",
    "James": "JAS",
    "1 Peter": "1PE",
    "2 Peter": "2PE",
    "1 John": "1JN",
    "2 John": "2JN",
    "3 John": "3JN",
    "Jude": "JUD",
    "Revelation": "REV",
}

# Prioritized French presets based on YouVersion popularity + common usage.
FRENCH_TRANSLATIONS = {
    "LSG": {
        "name": "La Sainte Bible par Louis Segond 1910",
        "bible_com_id": 93,
        "beblia_file": "FrenchBible.xml",
    },
    "S21": {
        "name": "La Bible Segond 21",
        "bible_com_id": 152,
        "beblia_file": "FrenchS21Bible.xml",
    },
    "BDS": {
        "name": "La Bible du Semeur 2015",
        "bible_com_id": 21,
        "beblia_file": "FrenchBDSBible.xml",
    },
    "BFC": {
        "name": "Bible en Francais Courant",
        "bible_com_id": 63,
        "beblia_file": "FrenchBFCBible.xml",
    },
    "PDV2017": {
        "name": "Parole de Vie 2017",
        "bible_com_id": 133,
        "beblia_file": "FrenchPDV2017Bible.xml",
    },
    "NBS": {
        "name": "Nouvelle Bible Segond",
        "bible_com_id": 104,
        "beblia_file": "FrenchNBSBible.xml",
    },
    "NEG79": {
        "name": "Nouvelle Edition de Geneve 1979",
        "bible_com_id": 106,
        "beblia_file": "FrenchNEG79Bible.xml",
    },
    "JND": {
        "name": "Bible J.N. Darby",
        "bible_com_id": 64,
        "beblia_file": "FrenchDarbyBible.xml",
    },
    "OST": {
        "name": "Ostervald",
        "bible_com_id": 131,
        "beblia_file": "FrenchOSTBible.xml",
    },
}

GRAPHQL_GET_BIBLE_VERSES = """
query GetBibleVerses($references: [String!], $id: Int!, $format: Format = HTML) {
  getBibleVerses(format: $format, id: $id, references: $references) {
    response {
      data {
        verses {
          content
        }
      }
    }
  }
}
"""


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def request_with_retry(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    last_error: Optional[Exception] = None

    for attempt in range(1, REQUEST_RETRY_COUNT + 1):
        try:
            response = session.request(method=method, url=url, timeout=REQUEST_TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < REQUEST_RETRY_COUNT:
                time.sleep(REQUEST_RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(f"Request failed after {REQUEST_RETRY_COUNT} attempts: {last_error}")


def ensure_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ensure_clean_folder(path: str) -> int:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        return 0

    deleted_count = 0
    for name in os.listdir(path):
        if not name.endswith(".json"):
            continue
        os.remove(os.path.join(path, name))
        deleted_count += 1

    return deleted_count


def combine_books(books_folder: str, output_file: str, translation_label: str) -> None:
    combined_data = {}

    for file_name in os.listdir(books_folder):
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(books_folder, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[+] Warning: cannot parse {file_name}: {exc}")
            continue

        combined_data.update(data)

    formatted = {
        "translation": translation_label,
        "books": [],
    }

    for book in BOOKS:
        if book not in combined_data:
            continue

        chapters = combined_data[book]
        chapter_list = []

        for chapter_key in sorted(chapters.keys(), key=lambda value: int(value)):
            verses = chapters[chapter_key]
            verse_list = []

            for verse_key in sorted(verses.keys(), key=lambda value: int(value)):
                verse_list.append(
                    {
                        "verse": int(verse_key),
                        "text": verses[verse_key],
                    }
                )

            chapter_list.append(
                {
                    "chapter": int(chapter_key),
                    "verses": verse_list,
                }
            )

        formatted["books"].append(
            {
                "name": book,
                "chapters": chapter_list,
            }
        )

    with open(output_file, "w", encoding="utf-8") as out_file:
        json.dump(formatted, out_file, indent=4, ensure_ascii=False)


def load_template_chapter_verse_counts() -> Dict[str, Dict[int, int]]:
    candidate_folders = [
        os.path.join("english", "KJV", "KJV_books"),
        os.path.join("english", "ASV", "ASV_books"),
        os.path.join("english", "WEB", "WEB_books"),
    ]

    template_folder = None
    for folder in candidate_folders:
        if os.path.isdir(folder):
            template_folder = folder
            break

    if not template_folder:
        raise RuntimeError("Could not find template books folder under english/*/*_books")

    counts: Dict[str, Dict[int, int]] = {}

    for file_name in os.listdir(template_folder):
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(template_folder, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(data, dict) or len(data) != 1:
            continue

        book_name = next(iter(data.keys()))
        chapters = data.get(book_name, {})
        if not isinstance(chapters, dict):
            continue

        chapter_counts: Dict[int, int] = {}
        for chapter_key, verses in chapters.items():
            if not str(chapter_key).isdigit() or not isinstance(verses, dict) or not verses:
                continue

            verse_numbers = [int(v) for v in verses.keys() if str(v).isdigit()]
            if not verse_numbers:
                continue

            chapter_counts[int(chapter_key)] = max(verse_numbers)

        if chapter_counts:
            counts[book_name] = chapter_counts

    if len(counts) < 66:
        raise RuntimeError("Template chapter counts look incomplete; expected 66 books")

    return counts


def fetch_verses_html(session: requests.Session, translation_id: int, references_expr: str) -> Optional[str]:
    payload = {
        "query": GRAPHQL_GET_BIBLE_VERSES,
        "variables": {
            "references": [references_expr],
            "id": translation_id,
            "format": "HTML",
        },
        "operationName": "GetBibleVerses",
    }

    response = request_with_retry(session, method="POST", url=GRAPHQL_URL, json=payload)

    try:
        data = response.json()
    except ValueError:
        return None

    if "errors" in data:
        return None

    verses = (
        data.get("data", {})
        .get("getBibleVerses", {})
        .get("response", {})
        .get("data", {})
        .get("verses", [])
    )

    if not verses:
        return None

    return verses[0].get("content")


def parse_verses_from_html(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    verses: Dict[str, str] = {}

    for verse_node in soup.select("span.verse[data-usfm]"):
        for removable in verse_node.select(
            "span.label, sup, span.note, span.crossreference, span.footnote, .footnote, .crossreference"
        ):
            removable.decompose()

        usfm_ref = verse_node.get("data-usfm", "")
        verse_number = usfm_ref.split(".")[-1]
        verse_text = normalize_space(verse_node.get_text(" ", strip=True))

        if verse_number.isdigit() and verse_text:
            verses[verse_number] = verse_text

    return verses


def fetch_chapter_with_fallback(
    session: requests.Session,
    translation_id: int,
    usfm_book: str,
    chapter_number: int,
    verse_numbers: List[int],
) -> Dict[str, str]:
    if not verse_numbers:
        return {}

    refs = "+".join(f"{usfm_book}.{chapter_number}.{verse_number}" for verse_number in verse_numbers)
    html = fetch_verses_html(session, translation_id, refs)

    if html:
        parsed = parse_verses_from_html(html)
        if parsed:
            return parsed

    if len(verse_numbers) == 1:
        return {}

    mid = len(verse_numbers) // 2
    left = fetch_chapter_with_fallback(session, translation_id, usfm_book, chapter_number, verse_numbers[:mid])
    right = fetch_chapter_with_fallback(session, translation_id, usfm_book, chapter_number, verse_numbers[mid:])

    merged = {}
    merged.update(left)
    merged.update(right)
    return merged


def download_via_bible_com(
    books_folder: str,
    translation_code: str,
    translation_id: int,
    translation_name: str,
    max_books: int,
    max_chapters: int,
    request_delay: float,
    resume: bool,
) -> Tuple[str, List[str]]:
    template_counts = load_template_chapter_verse_counts()

    books_queue = BOOKS[:]
    if max_books > 0:
        books_queue = books_queue[:max_books]

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
        }
    )

    failed_books: List[str] = []

    for index, book_name in enumerate(books_queue, start=1):
        output_path = os.path.join(books_folder, f"{book_name}.json")

        if resume and os.path.exists(output_path):
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (existing)", end="")
            continue

        usfm_book = USFM_BOOK_CODES.get(book_name)
        chapter_templates = template_counts.get(book_name, {})

        if not usfm_book or not chapter_templates:
            failed_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (template missing)", end="")
            continue

        chapter_numbers = sorted(chapter_templates.keys())
        if max_chapters > 0:
            chapter_numbers = chapter_numbers[:max_chapters]

        chapters_payload: Dict[str, Dict[str, str]] = {}

        for chapter_number in chapter_numbers:
            max_verse = chapter_templates[chapter_number]
            verse_numbers = list(range(1, max_verse + 1))

            parsed = fetch_chapter_with_fallback(
                session=session,
                translation_id=translation_id,
                usfm_book=usfm_book,
                chapter_number=chapter_number,
                verse_numbers=verse_numbers,
            )

            if parsed:
                ordered = {
                    str(verse_number): parsed[str(verse_number)]
                    for verse_number in sorted(int(v) for v in parsed.keys())
                }
                chapters_payload[str(chapter_number)] = ordered

            if request_delay > 0:
                time.sleep(request_delay)

        if not chapters_payload:
            failed_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (no chapters)", end="")
            continue

        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump({book_name: chapters_payload}, handle, indent=4, ensure_ascii=False)

        print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (ok)", end="")

    print()

    label = f"{translation_code}: {translation_name} [bible.com id={translation_id}]"
    return label, failed_books


def download_via_beblia(
    books_folder: str,
    translation_code: str,
    beblia_file: str,
    translation_name: str,
    max_books: int,
    max_chapters: int,
    resume: bool,
) -> Tuple[str, List[str]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        }
    )

    xml_url = f"{BEBLIA_RAW_BASE}/{beblia_file}"
    response = request_with_retry(session, method="GET", url=xml_url)
    content = response.content

    combined_data: Dict[str, Dict[str, Dict[str, str]]] = {}
    xml_stream = io.BytesIO(content)

    current_book_number: Optional[int] = None
    current_book_name: Optional[str] = None
    current_chapter: Optional[str] = None
    xml_translation_name: Optional[str] = None

    for event, elem in ET.iterparse(xml_stream, events=("start", "end")):
        tag = elem.tag

        if event == "start" and tag == "bible":
            xml_translation_name = elem.attrib.get("translation")

        if event == "start" and tag == "book":
            raw_number = elem.attrib.get("number", "").strip()
            if raw_number.isdigit():
                current_book_number = int(raw_number)
            else:
                current_book_number = None

            if current_book_number and 1 <= current_book_number <= len(BOOKS):
                current_book_name = BOOKS[current_book_number - 1]
                combined_data.setdefault(current_book_name, {})
            else:
                current_book_name = None

        if event == "start" and tag == "chapter":
            raw_chapter = elem.attrib.get("number", "").strip()
            current_chapter = raw_chapter if raw_chapter.isdigit() else None

            if current_book_name and current_chapter:
                combined_data[current_book_name].setdefault(current_chapter, {})

        if event == "end" and tag == "verse":
            raw_verse = elem.attrib.get("number", "").strip()
            if current_book_name and current_chapter and raw_verse.isdigit():
                verse_text = normalize_space(elem.text or "")
                if verse_text:
                    combined_data[current_book_name][current_chapter][raw_verse] = verse_text

        if event == "end":
            elem.clear()

    books_queue = BOOKS[:]
    if max_books > 0:
        books_queue = books_queue[:max_books]

    failed_books: List[str] = []

    for index, book_name in enumerate(books_queue, start=1):
        output_path = os.path.join(books_folder, f"{book_name}.json")

        if resume and os.path.exists(output_path):
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (existing)", end="")
            continue

        chapters = combined_data.get(book_name, {})
        if max_chapters > 0:
            chapters = {
                chapter_key: chapters[chapter_key]
                for chapter_key in sorted(chapters.keys(), key=lambda value: int(value))[:max_chapters]
            }

        if not chapters:
            failed_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (missing)", end="")
            continue

        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump({book_name: chapters}, handle, indent=4, ensure_ascii=False)

        print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (ok)", end="")

    print()

    parsed_name = xml_translation_name or translation_name
    label = f"{translation_code}: {parsed_name} [beblia:{beblia_file}]"
    return label, failed_books


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download French Bible translations from multiple sources into repository JSON format."
    )
    parser.add_argument("--translation-code", default="LSG", help="Preset code, e.g. LSG, S21, BDS, BFC, PDV2017")
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "bible-com", "beblia"],
        help="Source preference: auto tries beblia first then bible-com fallback",
    )
    parser.add_argument("--bible-com-id", type=int, default=0, help="Override Bible.com translation id")
    parser.add_argument("--beblia-file", default="", help="Override Beblia XML filename, e.g. FrenchS21Bible.xml")
    parser.add_argument("--max-books", type=int, default=0, help="Only download first N books (0 = all)")
    parser.add_argument("--max-chapters", type=int, default=0, help="Only download first N chapters per book (0 = all)")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help="Delay between chapter requests for bible-com mode",
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        help="Keep existing book JSON files and only download missing ones",
    )
    parser.add_argument(
        "--fresh",
        dest="resume",
        action="store_false",
        help="Delete existing book JSON files before downloading",
    )
    parser.set_defaults(resume=True)
    return parser.parse_args()


def resolve_translation(translation_code: str, bible_com_id: int, beblia_file: str) -> Tuple[str, str, int, str]:
    code = translation_code.strip().upper()

    if code in FRENCH_TRANSLATIONS:
        preset = FRENCH_TRANSLATIONS[code]
        name = str(preset["name"])
        resolved_bible_com_id = int(bible_com_id) if bible_com_id > 0 else int(preset["bible_com_id"])
        resolved_beblia_file = beblia_file.strip() if beblia_file.strip() else str(preset["beblia_file"])
        return code, name, resolved_bible_com_id, resolved_beblia_file

    name = f"Custom French Translation ({code})"
    resolved_bible_com_id = int(bible_com_id) if bible_com_id > 0 else 0
    resolved_beblia_file = beblia_file.strip()
    return code, name, resolved_bible_com_id, resolved_beblia_file


def main() -> None:
    args = parse_args()

    translation_code, translation_name, bible_com_id, beblia_file = resolve_translation(
        translation_code=args.translation_code,
        bible_com_id=args.bible_com_id,
        beblia_file=args.beblia_file,
    )

    root_folder = os.path.join("french", translation_code)
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

    translation_label = ""
    failed_books: List[str] = []

    if args.source == "auto":
        auto_errors = []

        if beblia_file:
            try:
                print(f"[+] Auto source step 1/2: beblia ({beblia_file})")
                translation_label, failed_books = download_via_beblia(
                    books_folder=books_folder,
                    translation_code=translation_code,
                    beblia_file=beblia_file,
                    translation_name=translation_name,
                    max_books=max(args.max_books, 0),
                    max_chapters=max(args.max_chapters, 0),
                    resume=args.resume,
                )
            except Exception as exc:
                auto_errors.append(f"beblia failed: {exc}")

        if not translation_label:
            if bible_com_id <= 0:
                joined = " | ".join(auto_errors) if auto_errors else "no source configured"
                raise RuntimeError(f"Auto mode could not run. {joined}")

            print(f"[+] Auto source step 2/2: bible-com (id={bible_com_id})")
            translation_label, failed_books = download_via_bible_com(
                books_folder=books_folder,
                translation_code=translation_code,
                translation_id=bible_com_id,
                translation_name=translation_name,
                max_books=max(args.max_books, 0),
                max_chapters=max(args.max_chapters, 0),
                request_delay=max(args.request_delay, 0.0),
                resume=args.resume,
            )

    elif args.source == "beblia":
        if not beblia_file:
            raise ValueError("--source beblia requires a known preset or --beblia-file")

        translation_label, failed_books = download_via_beblia(
            books_folder=books_folder,
            translation_code=translation_code,
            beblia_file=beblia_file,
            translation_name=translation_name,
            max_books=max(args.max_books, 0),
            max_chapters=max(args.max_chapters, 0),
            resume=args.resume,
        )

    else:
        if bible_com_id <= 0:
            raise ValueError("--source bible-com requires a known preset or --bible-com-id")

        translation_label, failed_books = download_via_bible_com(
            books_folder=books_folder,
            translation_code=translation_code,
            translation_id=bible_com_id,
            translation_name=translation_name,
            max_books=max(args.max_books, 0),
            max_chapters=max(args.max_chapters, 0),
            request_delay=max(args.request_delay, 0.0),
            resume=args.resume,
        )

    combine_books(books_folder=books_folder, output_file=output_file, translation_label=translation_label)
    print(f"[+] Combined output written to {output_file}")

    if failed_books:
        print(f"[+] Incomplete books ({len(failed_books)}): {', '.join(failed_books)}")


if __name__ == "__main__":
    main()
