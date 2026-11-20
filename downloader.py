
#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import requests


API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

FIELDS = ",".join([
    "paperId",
    "title",
    "authors",
    "year",
    "publicationDate",
    "venue",
    "url",
    "externalIds",
    "openAccessPdf",
])

# Inclusive publication-year window. Search walks this
# range from the newest year backward.
DEFAULT_YEAR_FROM = 2010
DEFAULT_YEAR_TO = 2026

# Relevance search returns at most this many hits per query.
MAX_RESULTS_PER_QUERY = 1000


def safe_filename(text, max_length=150):
    """
    Convert text into a filename-safe string.
    """

    text = text or "Untitled"

    # Characters forbidden in Windows filenames:
    # < > : " / \ | ? *
    text = re.sub(r'[<>:"/\\|?*]', "", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    # Avoid filenames ending in a period or space.
    return text[:max_length].rstrip(". ")


def pdf_filename(number, paper_id, prefix=""):
    """
    Build a short PDF filename.

    The paper title is not included. It is stored
    in the sibling JSON file.

    0001_PAPERID.pdf
    0001_Hydro_PAPERID.pdf
    """

    parts = [f"{number:04d}"]

    if prefix:
        short_prefix = safe_filename(
            prefix,
            max_length=40,
        )
        short_prefix = short_prefix.replace(" ", "_")

        if short_prefix:
            parts.append(short_prefix)

    parts.append(paper_id or "unknown")

    return "_".join(parts) + ".pdf"


def publication_path_parts(publication_date, year):
    """
    Split a publication date into YYYYMM and DD folders.

    2024-03-15 -> ("202403", "15")
    2024-03    -> ("202403", "00")
    2024       -> ("202400", "00")

    00 means Semantic Scholar did not provide that part.
    """

    text = str(publication_date or "").strip()

    match = re.fullmatch(
        r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?",
        text,
    )

    if match:
        year_text = match.group(1)
        month = match.group(2) or "00"
        day = match.group(3) or "00"

        if not 1 <= int(month) <= 12:
            month = "00"
            day = "00"

        if not 1 <= int(day) <= 31:
            day = "00"

        return f"{year_text}{month}", day

    if year:
        return f"{int(year):04d}00", "00"

    return None


def storage_directory(output_dir, year_month, day):
    """
    Store files under output_dir/YYYYMM/DD.

    The folders use the paper's publication date.
    """

    folder = (
        output_dir
        / year_month
        / day
    )

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return folder


def file_hash(path):
    """
    Calculate SHA-256 hash of a file.
    """

    sha256 = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            sha256.update(chunk)

    return sha256.hexdigest()


def create_session():
    """
    Create the HTTP session.

    No API key is required.
    """

    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "ResearchPDFDownloader/3.0 "
            "(academic research)"
        ),
        "Accept": "application/json",
    })

    return session


def years_newest_first(year_from, year_to):
    """
    Publication years from year_to down to year_from.
    """

    return range(year_to, year_from - 1, -1)


def paper_year(paper):
    """
    Return the paper's publication year as an int, or None.
    """

    value = paper.get("year")

    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def search_papers(
    query,
    offset,
    limit,
    session,
    year,
    max_retries=7,
):
    """
    Search Semantic Scholar for one publication year.

    Handles:
        429 rate limiting
        500 server errors
        502 bad gateway
        503 service unavailable
        504 gateway timeout

    One relevance query can return at most 1,000 hits.
    Callers move to the previous year after that window.
    """

    window = MAX_RESULTS_PER_QUERY - offset

    if window <= 0:
        return {
            "data": [],
            "total": 0,
            "next": None,
        }

    params = {
        "query": query,
        "offset": offset,
        "limit": min(limit, 100, window),
        "fields": FIELDS,
        "year": str(year),

        # Request papers for which Semantic Scholar
        # reports an open-access PDF.
        "openAccessPdf": "",
    }

    for attempt in range(max_retries):

        try:
            response = session.get(
                API_URL,
                params=params,
                timeout=30,
            )

        except requests.RequestException as exc:

            if attempt == max_retries - 1:
                raise

            wait = min(
                120,
                2 ** attempt,
            )

            print(
                f"  Search connection error: {exc}"
            )

            print(
                f"  Retrying in {wait:.0f} seconds..."
            )

            time.sleep(wait)
            continue

        # Successful request.
        if response.status_code == 200:
            return response.json()

        # Rate limited.
        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After"
            )

            if retry_after:
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = min(
                        120,
                        5 * (2 ** attempt),
                    )
            else:
                wait = min(
                    120,
                    5 * (2 ** attempt),
                )

            print()
            print(
                "  Semantic Scholar rate limit "
                "reached (HTTP 429)."
            )

            print(
                f"  Waiting {wait:.0f} seconds "
                "before retrying..."
            )

            time.sleep(wait)
            continue

        # Temporary server errors.
        if response.status_code in {
            500,
            502,
            503,
            504,
        }:

            if attempt == max_retries - 1:
                response.raise_for_status()

            wait = min(
                60,
                2 ** attempt,
            )

            print(
                f"  Semantic Scholar server error "
                f"({response.status_code})."
            )

            print(
                f"  Retrying in {wait:.0f} seconds..."
            )

            time.sleep(wait)
            continue

        # Other HTTP errors.
        response.raise_for_status()

    raise RuntimeError(
        "Semantic Scholar search failed after "
        f"{max_retries} attempts."
    )


def download_pdf(
    url,
    destination,
    session,
    max_retries=4,
):
    """
    Download and validate a PDF.

    Uses a .part file so interrupted downloads
    do not leave incomplete PDFs.
    """

    temporary = destination.with_suffix(
        destination.suffix + ".part"
    )

    for attempt in range(max_retries):

        try:

            with session.get(
                url,
                timeout=60,
                stream=True,
                allow_redirects=True,
            ) as response:

                # Handle rate limits and temporary
                # server errors.
                if response.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:

                    retry_after = response.headers.get(
                        "Retry-After"
                    )

                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except ValueError:
                            wait = min(
                                60,
                                3 * (2 ** attempt),
                            )
                    else:
                        wait = min(
                            60,
                            3 * (2 ** attempt),
                        )

                    print(
                        f"  PDF server returned "
                        f"HTTP {response.status_code}."
                    )

                    print(
                        f"  Retrying in "
                        f"{wait:.0f} seconds..."
                    )

                    time.sleep(wait)
                    continue

                response.raise_for_status()

                content_type = response.headers.get(
                    "content-type",
                    "",
                ).lower()

                first_chunk = next(
                    response.iter_content(
                        chunk_size=8192
                    ),
                    b"",
                )

                if not first_chunk:
                    return False, "Empty response"

                # Check both content type and PDF signature.
                is_pdf = (
                    "application/pdf" in content_type
                    or first_chunk.startswith(b"%PDF")
                )

                if not is_pdf:
                    return False, (
                        "Response is not a PDF "
                        f"(content-type: "
                        f"{content_type or 'unknown'})"
                    )

                with open(
                    temporary,
                    "wb",
                ) as file:

                    file.write(first_chunk)

                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            file.write(chunk)

            # Download completed.
            temporary.replace(destination)

            return True, "Downloaded"

        except requests.RequestException as exc:

            temporary.unlink(
                missing_ok=True
            )

            if attempt == max_retries - 1:
                return False, str(exc)

            wait = min(
                60,
                2 ** attempt,
            )

            print(
                f"  Download error: {exc}"
            )

            print(
                f"  Retrying in "
                f"{wait:.0f} seconds..."
            )

            time.sleep(wait)

        except OSError as exc:

            temporary.unlink(
                missing_ok=True
            )

            return False, str(exc)

    return False, "Download failed"


def write_metadata(pdf_path, record):
    """
    Write one JSON metadata file beside the PDF.

    The JSON name matches the PDF stem, so
    0001_PAPERID.pdf
    becomes
    0001_PAPERID.json
    """

    metadata_path = pdf_path.with_suffix(".json")

    metadata_path.write_text(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    return metadata_path


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download open-access research PDFs "
            "from Semantic Scholar."
        )
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Research query.",
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help=(
            "Number of successfully downloaded "
            "unique PDFs. Default: 50."
        ),
    )

    parser.add_argument(
        "--output",
        default="papers",
        help=(
            "Download directory. Files are stored by "
            "publication date as YYYYMM/DD inside "
            "this path. Default: papers"
        ),
    )

    parser.add_argument(
        "--prefix",
        default="",
        help=(
            "Optional short label added to filenames. "
            "The paper title is stored in the JSON file. "
            "Example: --prefix Hydro"
        ),
    )

    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help=(
            "Number of search results per page. "
            "Maximum: 100. Default: 100."
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help=(
            "Seconds between PDF downloads. "
            "Default: 2."
        ),
    )

    parser.add_argument(
        "--search-delay",
        type=float,
        default=3.0,
        help=(
            "Seconds between search pages. "
            "Default: 3."
        ),
    )

    parser.add_argument(
        "--year-from",
        type=int,
        default=DEFAULT_YEAR_FROM,
        help=(
            "Earliest publication year to include. "
            f"Default: {DEFAULT_YEAR_FROM}."
        ),
    )

    parser.add_argument(
        "--year-to",
        type=int,
        default=DEFAULT_YEAR_TO,
        help=(
            "Latest publication year to include. "
            "Search starts at this year and moves "
            "backward. "
            f"Default: {DEFAULT_YEAR_TO}."
        ),
    )

    args = parser.parse_args()

    if args.max_results <= 0:
        parser.error(
            "--max-results must be greater than 0"
        )

    if not 1 <= args.page_size <= 100:
        parser.error(
            "--page-size must be between 1 and 100"
        )

    if args.delay < 0:
        parser.error(
            "--delay cannot be negative"
        )

    if args.search_delay < 0:
        parser.error(
            "--search-delay cannot be negative"
        )

    if args.year_from > args.year_to:
        parser.error(
            "--year-from cannot be later than --year-to"
        )

    # Convert the output directory to an absolute path.
    script_dir = Path(__file__).resolve().parent

    output_path = Path(args.output)

    if output_path.is_absolute():
        output_dir = output_path
    else:
        output_dir = script_dir / output_path

    output_dir = output_dir.resolve()

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = create_session()

    # Clean the optional filename prefix.
    filename_prefix = safe_filename(
        args.prefix
    )

    print("=" * 70)
    print(
        "Semantic Scholar Open-Access PDF Downloader"
    )
    print("=" * 70)
    print()

    print(
        f"Query:           {args.query}"
    )

    print(
        f"Target PDFs:     {args.max_results}"
    )

    print(
        f"Download folder: {output_dir}"
    )

    print(
        "Date folders:    publication YYYYMM/DD"
    )

    print(
        "Metadata:        JSON file beside each PDF"
    )

    print(
        f"Filename prefix: "
        f"{filename_prefix or '(none)'}"
    )

    print(
        f"Page size:       {args.page_size}"
    )

    print(
        f"PDF delay:       {args.delay}s"
    )

    print(
        f"Search delay:    {args.search_delay}s"
    )

    print(
        f"Years:           {args.year_to} down to "
        f"{args.year_from}"
    )

    print()

    print(
        "API key:         Not required"
    )

    print()

    downloaded_records = []

    # Hashes of successfully downloaded PDFs.
    seen_hashes = set()

    # Semantic Scholar paper IDs already processed.
    seen_paper_ids = set()

    total_available = None
    stop_search = False

    for search_year in years_newest_first(
        args.year_from,
        args.year_to,
    ):

        if (
            stop_search
            or len(downloaded_records)
            >= args.max_results
        ):
            break

        print("=" * 70)
        print(
            f"Publication year {search_year}"
        )
        print("=" * 70)

        offset = 0

        while (
            len(downloaded_records)
            < args.max_results
        ):

            if offset >= MAX_RESULTS_PER_QUERY:

                print()
                print(
                    "Reached the 1,000-result "
                    f"limit for {search_year}."
                )

                break

            page_end = min(
                offset + args.page_size,
                MAX_RESULTS_PER_QUERY,
            )

            print("-" * 70)

            print(
                f"Searching {search_year} "
                f"results {offset + 1}-"
                f"{page_end}..."
            )

            try:

                result = search_papers(
                    query=args.query,
                    offset=offset,
                    limit=args.page_size,
                    session=session,
                    year=search_year,
                )

            except requests.RequestException as exc:

                print()
                print(
                    f"Search failed permanently: {exc}"
                )
                print()
                stop_search = True
                break

            except Exception as exc:

                print()
                print(
                    f"Unexpected search error: {exc}"
                )
                print()
                stop_search = True
                break

            papers = result.get(
                "data",
                [],
            )

            total_available = result.get(
                "total"
            )

            next_offset = result.get(
                "next"
            )

            print(
                f"Received {len(papers)} results."
            )

            if total_available is not None:

                print(
                    "Matching results reported by "
                    f"Semantic Scholar: "
                    f"{total_available:,}"
                )

            if not papers:

                print(
                    f"No more results for {search_year}."
                )

                break

            for paper in papers:

                if (
                    len(downloaded_records)
                    >= args.max_results
                ):
                    break

                paper_id = paper.get(
                    "paperId"
                )

                # Avoid processing the same paper twice.
                if (
                    paper_id
                    and paper_id in seen_paper_ids
                ):
                    continue

                if paper_id:
                    seen_paper_ids.add(
                        paper_id
                    )

                title = (
                    paper.get("title")
                    or "Untitled"
                )

                authors = [
                    author.get("name", "")
                    for author in (
                        paper.get("authors")
                        or []
                    )
                    if author.get("name")
                ]

                year = paper_year(paper)

                if year != search_year:

                    print(
                        f"  Skip: {title}"
                    )

                    print(
                        "  Year "
                        f"{year if year is not None else 'unknown'}"
                        f" does not match {search_year}."
                    )

                    continue

                venue = (
                    paper.get("venue")
                    or ""
                )

                external_ids = (
                    paper.get("externalIds")
                    or {}
                )

                doi = external_ids.get(
                    "DOI",
                    "",
                )

                paper_url = paper.get(
                    "url",
                    "",
                )

                open_access = (
                    paper.get("openAccessPdf")
                    or {}
                )

                pdf_url = open_access.get(
                    "url"
                )

                print()
                print(
                    f"Current successful downloads: "
                    f"{len(downloaded_records)}/"
                    f"{args.max_results}"
                )

                print(
                    f"Paper: {title}"
                )

                if not pdf_url:

                    print(
                        "  No PDF URL. Skipping."
                    )

                    continue

                # The number is based only on successful
                # unique downloads. The title stays in
                # the JSON file so the PDF name stays short.
                download_number = (
                    len(downloaded_records) + 1
                )

                filename = pdf_filename(
                    download_number,
                    paper_id,
                    filename_prefix,
                )

                publication_date = (
                    paper.get("publicationDate")
                    or ""
                )

                path_parts = publication_path_parts(
                    publication_date,
                    year,
                )

                if path_parts is None:

                    print(
                        "  No publication date. Skipping."
                    )

                    continue

                year_month, pub_day = path_parts

                if int(year_month[:4]) != search_year:

                    print(
                        "  Publication date "
                        f"{publication_date or year} "
                        f"does not match {search_year}. "
                        "Skipping."
                    )

                    continue

                day_dir = storage_directory(
                    output_dir,
                    year_month,
                    pub_day,
                )

                destination = (
                    day_dir / filename
                )

                # Prevent overwriting an existing file.
                if destination.exists():

                    counter = 2

                    while True:

                        base_name = (
                            destination.stem
                        )

                        candidate = (
                            day_dir
                            / (
                                f"{base_name} "
                                f"({counter}).pdf"
                            )
                        )

                        if not candidate.exists():

                            destination = candidate
                            break

                        counter += 1

                print(
                    f"  PDF URL: {pdf_url}"
                )

                success, message = download_pdf(
                    url=pdf_url,
                    destination=destination,
                    session=session,
                )

                if not success:

                    destination.unlink(
                        missing_ok=True
                    )

                    print(
                        f"  FAILED: {message}"
                    )

                    continue

                # Calculate SHA-256.
                try:

                    digest = file_hash(
                        destination
                    )

                except OSError as exc:

                    destination.unlink(
                        missing_ok=True
                    )

                    print(
                        f"  Hashing failed: {exc}"
                    )

                    continue

                # Detect duplicate PDF content.
                if digest in seen_hashes:

                    destination.unlink(
                        missing_ok=True
                    )

                    print(
                        "  DUPLICATE: PDF deleted."
                    )

                    continue

                seen_hashes.add(
                    digest
                )

                record = {
                    "number": download_number,
                    "paper_id": paper_id or "",
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "publication_date": publication_date,
                    "venue": venue,
                    "doi": doi,
                    "paper_url": paper_url,
                    "pdf_url": pdf_url,
                    "sha256": digest,
                    "filename": destination.name,
                }

                try:

                    metadata_path = write_metadata(
                        destination,
                        record,
                    )

                except OSError as exc:

                    destination.unlink(
                        missing_ok=True
                    )

                    seen_hashes.discard(
                        digest
                    )

                    print(
                        f"  Metadata write failed: {exc}"
                    )

                    continue

                # The PDF is now officially considered
                # a successful download.
                downloaded_records.append(
                    record
                )

                print()
                print(
                    "  SUCCESS!"
                )

                print(
                    f"  Saved: {destination.name}"
                )

                print(
                    f"  Metadata: {metadata_path.name}"
                )

                print(
                    f"  Progress: "
                    f"{len(downloaded_records)}/"
                    f"{args.max_results}"
                )

                print(
                    f"  Directory: {day_dir}"
                )

                if (
                    len(downloaded_records)
                    >= args.max_results
                ):
                    break

                if args.delay > 0:

                    time.sleep(
                        args.delay
                    )

            # Target reached.
            if (
                len(downloaded_records)
                >= args.max_results
            ):
                break

            # Get the next search page.
            if next_offset is not None:

                offset = next_offset

            else:

                offset += len(papers)

            # Fewer results than requested means this
            # publication year has no further pages.
            if (
                len(papers)
                < args.page_size
            ):

                print()
                print(
                    f"Finished publication year "
                    f"{search_year}."
                )

                break

            print()
            print(
                f"Waiting {args.search_delay}s "
                "before the next search page..."
            )

            if args.search_delay > 0:

                time.sleep(
                    args.search_delay
                )

        if (
            stop_search
            or len(downloaded_records)
            >= args.max_results
        ):
            break

        if args.search_delay > 0:

            print()
            print(
                f"Waiting {args.search_delay}s "
                "before the previous year..."
            )

            time.sleep(
                args.search_delay
            )

    print()
    print("=" * 70)
    print("FINISHED")
    print("=" * 70)

    print(
        f"Downloaded PDFs: "
        f"{len(downloaded_records)}"
    )

    print(
        f"Download folder: "
        f"{output_dir}"
    )

    print("=" * 70)

    if (
        len(downloaded_records)
        < args.max_results
    ):

        print()
        print(
            "WARNING:"
        )

        print(
            f"Requested {args.max_results} PDFs, "
            f"but only "
            f"{len(downloaded_records)} "
            "were successfully downloaded."
        )

        print(
            "Each saved PDF has a matching "
            "JSON metadata file."
        )


if __name__ == "__main__":
    main()
