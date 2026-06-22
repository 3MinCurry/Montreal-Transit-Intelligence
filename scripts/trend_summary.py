import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mti.config import STM_DELIMITER, STM_ENCODING
from mti.stm_cleaning import clean_stm_dataframe

stm = pd.read_csv(ROOT / "data/raw/stm_incidents_metro.csv", sep=STM_DELIMITER, encoding=STM_ENCODING)
clean = clean_stm_dataframe(stm)
clean["date"] = pd.to_datetime(clean["date"])
clean["year"] = clean["date"].dt.year

daily = clean.groupby(clean["date"].dt.date).size().reset_index(name="incidents")
daily.columns = ["date", "incidents"]
daily["date"] = pd.to_datetime(daily["date"])
daily["year"] = daily["date"].dt.year

yearly = daily.groupby("year")["incidents"].agg(total="sum", mean_per_day="mean", days="count")

monthly_mean = daily.assign(month=daily["date"].dt.month).groupby("month")["incidents"].mean()

early = daily[daily["year"].between(2019, 2021)]["incidents"].mean()
mid = daily[daily["year"].between(2022, 2023)]["incidents"].mean()
recent = daily[daily["year"] >= 2024]["incidents"].mean()

print("YEARLY")
print(yearly.round(2).to_string())
print()
print(f"Mean incidents/day: 2019-2021={early:.2f}, 2022-2023={mid:.2f}, 2024+={recent:.2f}")
print()
print("MEAN DAILY BY CALENDAR MONTH")
for m in range(1, 13):
    print(f"  {m:02d}: {monthly_mean[m]:.2f}")
print()
lines = clean[clean["line_name"].isin(["Green", "Orange", "Yellow", "Blue"])]
print("LINE TOTALS (train incidents, single-line only)")
print(lines["line_name"].value_counts().to_string())
