# PubMed PDF Batch Downloader

A desktop GUI tool that batch-downloads open-access PDFs from **PubMed Central (PMC)** using browser automation.

The tool reads a tab-separated (TSV) list exported from PubMed/NCBI, visits each article's PMC page, clicks the "PDF" download button via Selenium-driven Microsoft Edge, renames the file to `Year_Title.pdf`, and generates a detailed Excel download report.

## Features

- **GUI application** (Tkinter): select list file, choose save directory, parse, download with live log and progress bar
- **TSV input support** for PubMed exports: `PMID | DOI | PMCID | Title | Year`
- **PMC PDF auto-download** with a 60-second per-file timeout and retry-friendly renaming
- **Duplicate skip**: already-downloaded PDFs (same filename) are skipped automatically (allowing resume of interrupted batches)
- **Excel report** (`下载报告_YYYYMMDD_HHMMSS.xlsx`) with per-paper status, failure reason, and a clickable PubMed URL
- **Auxiliary `id_conv.py`** script: matches IDs from a download report's PMIDs against the official `PMC-ids.csv` archive to recover missing DOI / PMCID values (does a left-join on PMID)

## Requirements

- Python 3.8+
- Microsoft **Edge** browser (the driver version must match your Edge version)
- Dependencies: `pip install -r requirements.txt`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Edge WebDriver (critical)

Download the `msedgedriver.exe` matching your installed Edge version from the
[Microsoft Edge WebDriver page](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/) (or [Microsoft Edge - Webdriver](https://msedgedriver.microsoft.com/catalog/index.html)) and place it in the **same folder as `pubmed_downloader.py`**.

> Version mismatch (`SessionNotCreatedException`) after an Edge auto-update is the most common failure — just re-download the matching driver.

## Usage

```bash
python pubmed_downloader.py
```

1. Click **浏览 (Browse)** and select the TSV list file (e.g. `examples/sample_pubmed.tsv`).
2. Choose the save directory (default: `~/Desktop/PubMedPDFs`).
3. Click **解析文件 (Parse)** — the log shows how many papers were read and how many have a PMCID.
4. Click **开始下载 (Start Download)**. The controlled Edge window opens, downloads each PDF, renames it, and records results.
5. A report Excel file is generated in the save directory when the batch finishes.

### Input file format

Tab-separated, first row is the header (columns are 0-indexed):

| Col | Field  | Example                     |
|-----|--------|-----------------------------|
| 0   | PMID   | 38371285                    |
| 1   | DOI    | 10.3390/plants14223495      |
| 2   | PMCID  | PMC10847389 (or `None`)     |
| 3   | Title  | Transcription Factor ...    |
| 4   | Year   | 2025                        |

Papers without a PMCID are reported as failed (`无 PMC 号`) in the report — use `id_conv.py` to recover missing PMCIDs/DOIs from the official `PMC-ids.csv` archive, then re-run.

### Recovering IDs (optional, id_conv.py)

```bash
python id_conv.py
```

Reads `id_conv_before.csv` (must contain a `PMID` column, e.g. a previous download report) and left-joins against `PMC-ids.csv` (official archive from http://www.ncbi.nlm.nih.gov/pmc/tools/ftp/), writing `id_conv_after.csv` with columns `PMID, DOI, PMCID`.

## Output

Save directory contains:

- `Year_Title.pdf` — downloaded article PDFs (files with invalid characters in the title get `_` substituted, capped at 150 chars)
- `下载报告_YYYYMMDD_HHMMSS.xlsx` — per-paper result report

## Notes & Limitations

- Downloads **open-access PMC content only** (determined by what the PMC page exposes); closed-access items will report "未找到PDF下载按钮".
- If network is slow, a paper may time out after 60 s — re-running the tool skips already-saved files and retries the rest.
- Google no longer — links in the report point to `https://pubmed.ncbi.nlm.nih.gov/<PMID>/` for manual follow-up.

## License

MIT — see [LICENSE](LICENSE).
