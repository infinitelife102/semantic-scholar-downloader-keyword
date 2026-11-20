# Semantic Scholar Open-Access PDF Downloader

A Python command-line tool for searching [Semantic Scholar](https://www.semanticscholar.org/) and downloading openly accessible research papers as PDF files, with a JSON metadata file beside each PDF.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-Responsible--Use-lightgrey)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

`downloader.py` runs one search. `download_papers.py` runs twelve hydro and thermal power searches in sequence. Both keep only PDFs that Semantic Scholar marks as open access. A download counts only when the response is a real PDF and its contents are not an exact duplicate of a file already saved in that run.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Single Search](#single-search)
- [Hydro and Thermal Batch](#hydro-and-thermal-batch)
- [Command-Line Options](#command-line-options)
- [Output Layout](#output-layout)
- [Filenames and Metadata](#filenames-and-metadata)
- [Edge Cases](#edge-cases)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Responsible Use](#responsible-use)

---

## Features

| Category | What it does |
|---|---|
| **Search** | Walks publication years from `--year-to` down to `--year-from` (default 2026 down to 2010). Within a year, Semantic Scholar relevance order is unchanged. |
| **Year window** | Keeps a paper only when its publication year matches the year being searched. Each year can return at most 1,000 relevance-ranked hits. |
| **Download** | Fetches the open-access PDF through a `.part` file, then renames it when the download finishes. |
| **Validation** | Accepts a file when the response content type is PDF or the body starts with `%PDF`. HTML pages are rejected. |
| **Deduplication** | SHA-256 hash, compared with successful downloads in the same run. |
| **Retries** | Waits and retries HTTP 429. Retries 500, 502, 503, and 504 with exponential backoff and honors `Retry-After`. |
| **Metadata** | Writes one JSON file next to each successful PDF. |
| **Names** | `0001_PREFIX_PAPERID.pdf`. The title stays in the JSON file. |
| **Folders** | `YYYYMM/DD` from the paper's publication date, inside the output directory. |

---

## Requirements

- Python 3.9 or newer
- Internet access
- Package: `requests`

The current code does not send a Semantic Scholar API key. Unauthenticated search calls share one public rate limit and often return HTTP 429.

---

## Project Structure

```text
semantic-scholar-pdf-downloader/
├── downloader.py          # one search
├── download_papers.py     # twelve hydro and thermal searches
├── README.md
└── papers/                # created on first run, unless another path is set
    └── hydro/
        └── turbine-efficiency/
            └── 202605/
                └── 05/
                    ├── 0001_Hydro_<paper id>.pdf
                    └── 0001_Hydro_<paper id>.json
```

`papers/` does not need to be created by hand. `download_papers.py` adds `hydro/` or `thermal/` and a topic folder under the output root. `downloader.py` writes directly into the directory given by `--output`.

---

## Installation

### 1. Install Python

Download from [python.org/downloads](https://www.python.org/downloads/). On Windows, check **Add Python to PATH** during setup.

```bash
python --version
```

If `python` is not recognized, try `python3 --version`.

### 2. Install dependencies

```bash
pip install requests
```

If `pip` is not recognized:

```bash
python -m pip install requests
```

---

## Single Search

```bash
python downloader.py --query "hydropower turbine efficiency improvement"
```

This tries to save **50** successful, unique PDFs. `--max-results` counts successful unique PDFs, not search hits examined.

```bash
python downloader.py --query "hydropower turbine efficiency improvement" --max-results 20
```

A relative `--output` is resolved from the directory that contains `downloader.py`, not from the shell's current directory. An absolute path is used as given.

---

## Hydro and Thermal Batch

`download_papers.py` calls `downloader.py` once per search. The default is 420 successful PDFs per search, 12 searches, about 5,000 PDFs. Each search still walks 2026 down to 2010 and stops when its own PDF target is reached.

Set the folder in either place. `--output` overrides `OUTPUT_DIR`.

```python
# top of download_papers.py
OUTPUT_DIR = r"D:\Research\PowerPapers"
```

```powershell
python download_papers.py --output "D:\Research\PowerPapers"
```

Leave both empty and the files go to `papers/` next to the script. A relative `--output` is resolved from the current working directory.

Try a small batch before a full run:

```powershell
python download_papers.py --output "D:\Research\PowerPapers" --per-query 2
```

| Group | Folder | Query |
|---|---|---|
| hydro | `turbine-efficiency` | hydropower turbine efficiency improvement |
| hydro | `francis` | Francis turbine performance upgrade |
| hydro | `kaplan` | Kaplan turbine efficiency optimization |
| hydro | `pumped-storage` | pumped storage hydropower efficiency |
| hydro | `generator` | hydroelectric generator capacity uprating |
| hydro | `small-hydro` | small hydropower output optimization |
| thermal | `plant-efficiency` | thermal power plant efficiency improvement |
| thermal | `steam-turbine` | steam turbine heat rate improvement |
| thermal | `coal` | coal fired power plant efficiency upgrade |
| thermal | `ccgt` | combined cycle gas turbine efficiency |
| thermal | `boiler` | boiler efficiency improvement thermal power |
| thermal | `supercritical` | supercritical power plant efficiency |

Hydro filenames use the prefix `Hydro`. Thermal filenames use `Thermal`. Duplicate detection does not carry from one search to the next, so the same PDF can be saved again under another topic folder.

A full run can take many hours. The 2 second pause between PDFs is only the wait; failed downloads and HTTP 429 retries add more time.

---

## Command-Line Options

### `downloader.py`

| Option | Description | Default |
|---|---|---|
| `--query` | Research query. Required. | — |
| `--max-results` | Successful unique PDFs to download | `50` |
| `--output` | Directory for PDFs and JSON files. Publication-date folders are created inside it. | `papers` |
| `--prefix` | Short filename label. Spaces become underscores. Longer than 40 characters is cut. | *(none)* |
| `--page-size` | Search results per API call. Maximum `100`. | `100` |
| `--delay` | Seconds between PDF downloads | `2` |
| `--search-delay` | Seconds between search pages, and between publication years | `3` |
| `--year-from` | Earliest publication year | `2010` |
| `--year-to` | Latest publication year. Search starts here and moves backward. | `2026` |

```bash
python downloader.py --help
```

### `download_papers.py`

| Option | Description | Default |
|---|---|---|
| `--output` | Root folder for all twelve searches. Overrides `OUTPUT_DIR`. | `OUTPUT_DIR`, or `papers` next to the script |
| `--per-query` | Successful PDFs for each search | `420` |
| `--year-from` | Earliest publication year | `2010` |
| `--year-to` | Latest publication year | `2026` |
| `--delay` | Seconds between PDF downloads | `2` |
| `--search-delay` | Seconds between search pages | `3` |

```bash
python download_papers.py --help
```

---

## Output Layout

Folders use the paper's publication date, not the day the file was downloaded.

```text
D:\Research\PowerPapers\hydro\francis\202403\15\0001_Hydro_<paper id>.pdf
D:\Research\PowerPapers\hydro\francis\202403\15\0001_Hydro_<paper id>.json
```

`202403` is March 2024. `15` is the publication day.

| Semantic Scholar date | Folder |
|---|---|
| `2024-03-15` | `202403/15` |
| `2024-03` (no day) | `202403/00` |
| `2024` (year only) | `202400/00` |

A paper with no usable year is skipped. The JSON field `publication_date` stores the date string Semantic Scholar returned. A run that passes midnight does not change the folder; the publication date does.

`downloader.py` examples:

```bash
python downloader.py --query "hydropower turbine efficiency improvement" --output "D:\Research\Hydro"
# → D:\Research\Hydro\202403\15\

python downloader.py --query "hydropower turbine efficiency improvement" --output "research"
# → <directory of downloader.py>\research\202403\15\
```

---

## Filenames and Metadata

```text
0001_PAPERID.pdf
0001_Hydro_PAPERID.json
```

| Example | With `--prefix Hydro` |
|---|---|
| `0001_<paper id>.pdf` | `0001_Hydro_<paper id>.pdf` |
| `0001_<paper id>.json` | `0001_Hydro_<paper id>.json` |

The number counts successful unique downloads in that run. It is zero-padded to four digits. The paper ID is the full Semantic Scholar ID. Skipped, failed, and duplicate results do not take a number.

The JSON file is written as soon as that PDF succeeds. An interrupted run keeps the pairs already finished.

```json
{
  "number": 1,
  "paper_id": "6353ae621c562dabfd6b15c23a5d6c21cede34c2",
  "title": "Example Paper Title",
  "authors": ["Ada Lovelace", "Alan Turing"],
  "year": 2024,
  "publication_date": "2024-03-15",
  "venue": "Example Journal",
  "doi": "10.1000/example",
  "paper_url": "https://www.semanticscholar.org/paper/6353ae621c562dabfd6b15c23a5d6c21cede34c2",
  "pdf_url": "https://example.org/paper.pdf",
  "sha256": "…",
  "filename": "0001_Hydro_6353ae621c562dabfd6b15c23a5d6c21cede34c2.pdf"
}
```

| Field | Description |
|---|---|
| number | Successful download order in this run |
| paper_id | Semantic Scholar paper ID |
| title | Paper title |
| authors | Author names |
| year | Publication year |
| publication_date | Date string from Semantic Scholar (`2024-03-15`, `2024-03`, `2024`, or empty) |
| venue | Journal or conference |
| doi | DOI, if available |
| paper_url | Semantic Scholar page |
| pdf_url | URL the PDF was downloaded from |
| sha256 | SHA-256 of the PDF |
| filename | PDF filename on disk |

Failed downloads, HTML responses, publisher refusals, and duplicates leave neither a PDF nor a JSON file.

---

## Edge Cases

**Duplicates.** Each successful PDF is hashed with SHA-256. The same bytes later in that run are deleted and not counted. A new run, or another topic folder in `download_papers.py`, starts with an empty hash set.

**PDF check.** The response must report a PDF content type or begin with `%PDF`. An HTML page is rejected.

**Partial files.** Bytes are written to `0001_Hydro_<paper id>.pdf.part` and renamed only after the download finishes.

**Rate limits.** HTTP 429 is retried with a growing wait, up to 120 seconds, for seven attempts. The server `Retry-After` header is used when it is present. After seven failed search attempts the search stops. `download_papers.py` then continues with the next query when `downloader.py` exits normally.

**Publisher blocks.** A Semantic Scholar API key would not change an HTTP 403 or a connection reset from the site that hosts the PDF. Those URLs are skipped.

**Pagination.** Each year is requested in pages of `--page-size` (maximum 100). The year ends when its hits run out or the 1,000-hit relevance cap is reached. The tool then waits `--search-delay` seconds and continues with the previous year.

---

## Examples

```bash
# 50 PDFs next to downloader.py, under papers/YYYYMM/DD
python downloader.py --query "hydropower turbine efficiency improvement"

# 10 PDFs
python downloader.py --query "hydropower turbine efficiency improvement" --max-results 10

# Absolute output directory and a short prefix
python downloader.py --query "steam turbine heat rate improvement" --max-results 50 --output "D:\Research\Thermal" --prefix Thermal

# Longer pauses when HTTP 429 is frequent
python downloader.py --query "hydropower turbine efficiency improvement" --max-results 50 --delay 5 --search-delay 10
```

PowerShell:

```powershell
python downloader.py `
    --query "hydropower turbine efficiency improvement" `
    --max-results 50 `
    --output "D:\Research\Hydro" `
    --prefix Hydro
```

Batch, small trial, then the default target:

```powershell
python download_papers.py --output "D:\Research\PowerPapers" --per-query 2
python download_papers.py --output "D:\Research\PowerPapers"
```

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `'python' is not recognized` | Try `python3 --version`, or reinstall Python with **Add Python to PATH** checked. |
| `pip` is not recognized | `python -m pip install requests` |
| `ModuleNotFoundError: requests` | `python -m pip install requests` |
| Repeated HTTP 429 | The public search pool is shared. Increase `--search-delay` (for example `10`). Wait before starting the next run. This project does not attach an API key. |
| `Search failed permanently` or `search failed after 7 attempts` | The search gave up after repeated 429 or server errors. Check the network, then retry later with a higher `--search-delay`. |
| HTTP 403 or `ConnectionResetError` on a PDF URL | The publisher refused or dropped the download. The paper is skipped. |
| `Response is not a PDF` | The URL returned HTML. The paper is skipped. |
| Fewer files than requested | Some hits have no working PDF, fail validation, or are duplicates. The run stops when the year range is exhausted or the search fails. |
| Files land in `papers/` instead of the chosen disk | Set `OUTPUT_DIR` in `download_papers.py`, or pass `--output` with a full path. |

---

## Responsible Use

This tool is for legitimate academic and research use. It downloads PDFs only from URLs Semantic Scholar reports as open access. It does not bypass paywalls, circumvent authentication, defeat access controls, or break website security.

Users are responsible for copyright law, license terms, institutional policy, and the [Semantic Scholar API terms](https://api.semanticscholar.org/api-docs/).

**API:** [`api.semanticscholar.org/graph/v1`](https://api.semanticscholar.org/graph/v1) · **Docs:** [api.semanticscholar.org/api-docs](https://api.semanticscholar.org/api-docs/)
