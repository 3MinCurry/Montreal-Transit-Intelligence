# Databricks Free Edition — setup guide

Run **Montreal Transit Intelligence** on Databricks with **PySpark + Delta Lake + Unity Catalog Volumes**.

> **Why Databricks here:** same analytics as local pandas, but ELT runs as a **medallion pipeline** (bronze → silver → gold) — good for a data-engineering portfolio even when the dataset fits on a laptop.

> **Important:** Free Edition **disables `/FileStore` and public DBFS**.  
> Use a **Unity Catalog Volume** at `/Volumes/workspace/default/mti/` (or `main`).

---

## Checklist (copy this)

- [ ] Sign up for [Databricks Free Edition](https://login.databricks.com/signup?provider=DB_FREE_TIER)
- [ ] Link GitHub repo in **Workspace → Repos**
- [ ] Run `.\scripts\download_data.ps1` on your PC
- [ ] Run **`notebooks/00b_bootstrap_check`** → creates volume + folders
- [ ] Upload **5 CSVs** to `{VOLUME}/raw/` (see below)
- [ ] Run **`notebooks/00_run_full_pipeline`** → Delta + FINDINGS + charts
- [ ] Download `outputs/` from the volume for README images / local review

---

## Step 0 — Prepare data on your PC

```powershell
cd c:\Users\Kyujin\montreal-transit-intelligence
pip install -e .
.\scripts\download_data.ps1
```

This creates:

| File | Required | Purpose |
|------|----------|---------|
| `data/raw/stm_incidents_metro.csv` | **Yes** | STM train incidents |
| `data/raw/weather_yul_daily.csv` | **Yes** | YUL daily weather |
| `data/raw/canadiens_home_games.csv` | Recommended | Canadiens calendar lifts |
| `data/raw/requests_311_daily.csv` | Recommended | 311 rider-experience layer |
| `data/raw/stm_experience_yearly.csv` | Recommended | STM published experience % |

Source for the experience file: `data/reference/stm_experience_yearly.csv` (copied to `data/raw/` by `download_data.ps1`).

---

## Step 1 — Sign up & link repo

1. [Databricks Free Edition signup](https://login.databricks.com/signup?provider=DB_FREE_TIER) — Google or Microsoft, no credit card.
2. **Workspace → Repos → Add Repo** → your GitHub URL.
3. Before each run: **Pull** latest `main`.

---

## Step 2 — Bootstrap storage

Open **`notebooks/00b_bootstrap_check`** → **Run all**.

Creates:

```text
/Volumes/{workspace|main}/default/mti/
  raw/
  delta/bronze/
  delta/silver/
  delta/gold/
  outputs/
```

Note the printed path (often **`workspace`**, not `main`, on Free Edition).

---

## Step 3 — Upload CSVs to the volume

**Catalog → {workspace|main} → default → mti → raw → Upload**

Exact filenames (case-sensitive):

```text
/Volumes/workspace/default/mti/raw/stm_incidents_metro.csv
/Volumes/workspace/default/mti/raw/weather_yul_daily.csv
/Volumes/workspace/default/mti/raw/canadiens_home_games.csv
/Volumes/workspace/default/mti/raw/requests_311_daily.csv
/Volumes/workspace/default/mti/raw/stm_experience_yearly.csv
```

Verify:

```python
dbutils.fs.ls("/Volumes/workspace/default/mti/raw")
```

Replace `workspace` with your catalog if bootstrap printed `main`.

---

## Step 4 — Bootstrap check

Run **`00b_bootstrap_check`** again. Expect:

```text
[OK] stm_csv: ...
[OK] weather_csv: ...
[OK] canadiens_csv (optional): ...   # or [FAIL] — Canadiens section skipped
[OK] requests_311_daily (optional): ...  # or [FAIL] — 311 charts/sections skipped
```

Only STM + weather are **required** to run.

---

## Step 5 — Run the full pipeline

Open **`notebooks/00_run_full_pipeline`** → **Run all**.

| Stage | Technology | Output |
|-------|------------|--------|
| Ingest | Spark read CSV | `delta/bronze/` |
| Clean | PySpark transforms | `delta/silver/` |
| Aggregate | Gold fact tables | `delta/gold/` |
| Analytics | pandas (shared `src/mti/`) | FINDINGS, charts |

### Outputs

| Output | Path |
|--------|------|
| Delta tables | `/Volumes/.../mti/delta/` |
| Charts (PNG) | `/Volumes/.../mti/outputs/` |
| FINDINGS | `FINDINGS.md` in the Repo checkout |

Preview gold data:

```python
display(
    spark.read.format("delta")
    .load("/Volumes/workspace/default/mti/delta/gold/fact_incidents_daily")
    .limit(5)
)
```

---

## Step 6 — Bring outputs back to your PC

Charts live on the **volume**, not on your laptop automatically.

1. **Catalog → mti → outputs/** → download PNGs
2. Or copy into `docs/images/` for README (local pipeline does this automatically)
3. Run **Streamlit locally** with the same raw CSVs: `python -m streamlit run scripts/run_dashboard.py`

---

## Architecture (what you're demonstrating)

```text
  CSV (Volume raw/)
       │
       ▼  PySpark
  bronze Delta  ──►  silver Delta  ──►  gold Delta
       │                                    │
       └────────────────────────────────────┘
                          │
                          ▼  pandas (same src/mti/analysis.py)
                    FINDINGS + charts
```

Local `python scripts/run_pipeline.py` skips Spark and reads CSV directly. **Same numbers, different ELT path.**

---

## Optional: step-by-step notebooks

| Notebook | Stage |
|----------|--------|
| `01_ingest.py` | CSV → bronze |
| `02_clean.py` | bronze → silver |
| `03_aggregate.py` | silver → gold |
| `04_weather_analysis.py` | exploration |

`00_run_full_pipeline` runs ingest + clean + aggregate + analytics in one go.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Permission denied: '/FileStore'` | Expected on Free Edition — use **Volumes** only |
| Volume not found | Run `00b_bootstrap_check` or create volume `mti` in Catalog UI |
| `[FAIL] stm_csv` | Wrong path or filename — must be under `{VOLUME}/raw/` |
| Catalog is `workspace` not `main` | Normal — use the path bootstrap prints |
| `Old spark_pipeline cached` | Repo → **Pull**, then **Detach & Re-attach** notebook |
| Canadiens / 311 sections missing | Upload optional CSVs; run `download_data.ps1` locally first |
| 311 download on Databricks | Run `python scripts/download_311.py` **locally**, upload the daily CSV |

Set volume override if needed:

```python
import os
os.environ["MTI_VOLUME_BASE"] = "/Volumes/workspace/default/mti"
```

---

## Quick reference

```text
DO NOT USE (Free Edition):  /FileStore/...
USE INSTEAD:                /Volumes/workspace/default/mti/raw/
Delta:                      /Volumes/workspace/default/mti/delta/
Charts:                     /Volumes/workspace/default/mti/outputs/
First notebook:             00b_bootstrap_check
Pipeline notebook:          00_run_full_pipeline
```

---

## Portfolio one-liner

> Dual-path STM metro reliability analytics: **local pandas** for fast iteration and **Databricks Free Edition** (PySpark, Delta Lake, Unity Catalog Volumes) for production-style medallion ELT — shared analytics layer, reproducible FINDINGS.
