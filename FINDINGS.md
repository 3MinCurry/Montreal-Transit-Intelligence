# Montreal Transit Analysis — Findings

Analysis window: **2019-01-01** through the last complete month in the dataset.

**Personal project for curiosity and fun** — descriptive analytics only; correlations and associations, **not causation**. Not affiliated with STM and not for operational use.

This report frames **STM metro reliability** as a multi-factor question: **weather**, **calendar context**, **passenger-related causes**, and **operations/equipment** patterns (2019+ train incidents joined to YUL weather).

## Executive summary

- Custom network reliability score: **72.4/100** (month-adjusted incidents + disruption vs seasonal medians).
- Weather × cause: snow days **raise Clientèle** (1.25×) but **lower Équipements fixes** (0.768×).
- Operations trend: Cause mix shifted 2019→2025: rising share: Clientèle, Équipements fixes; falling share: Matériel roulant, Exploitation trains.

- **COVID-era dip and recovery:** Mean daily incidents fell from 13.9 (2019) to 10.0 (2020–2021), then recovered to 13.8 in 2024.
- **Line concentration:** Green line accounts for 41% of single-line train incidents; most incidents on Green, most disruption minutes on Green.
- **Primary causes:** Top causes: Clientèle (54%), Équipements fixes (17%), Matériel roulant (14%).
- **Season & weather:** Winter daily rate is **1.213×** summer; snow (D0/D−1) lift is **1.115×** baseline.
- **Rush hours:** **20%** of weekday incidents occur 7–9 AM; **16%** occur 4–6 PM.
- **Week rhythm:** Weekday daily rate is **1.311×** the weekend rate.

## Hypotheses

### Season & calendar

#### H1: Winter vs summer daily incident rate
- **Metric:** `winter_mean / summer_mean`
- **Result:** **1.213**
- **Detail:** Winter mean=13.26/day, summer mean=10.93/day

#### H7: Weekday vs weekend daily incident rate
- **Metric:** `weekday_mean / weekend_mean`
- **Result:** **1.311**
- **Detail:** Weekday mean=12.70/day, weekend mean=9.68/day

### Rush hour

#### H2: Weekday AM rush concentration (7–9 AM)
- **Metric:** `share_of_weekday_incidents_7_9am`
- **Result:** **0.202**
- **Detail:** Peak weekday hour=8:00; AM rush share=20.2%

#### H8: Weekday PM rush concentration (4–6 PM)
- **Metric:** `share_of_weekday_incidents_4_6pm`
- **Result:** **0.162**
- **Detail:** PM rush share=16.2% of weekday train incidents

### Weather associations

#### H3: Snow day (D0 or D-1) associated with higher incidents
- **Metric:** `mean_incidents_snow / mean_incidents_non_snow`
- **Result:** **1.115**
- **Detail:** Snow-or-prev mean=13.10/day, baseline mean=11.75/day

#### H4: Heavy rain day (≥15 mm) associated with higher incidents
- **Metric:** `mean_incidents_rain / mean_incidents_dry`
- **Result:** **1.046**
- **Detail:** Heavy-rain mean=12.35/day, baseline mean=11.81/day

#### H5: Cold snap day (max ≤ -15 °C) associated with higher incidents
- **Metric:** `mean_incidents_cold / mean_incidents_mild`
- **Result:** **1.067**
- **Detail:** Cold-snap mean=12.62/day, baseline mean=11.83/day

#### H6: Freeze-thaw day associated with higher incidents
- **Metric:** `mean_incidents_freeze_thaw / mean_incidents_other`
- **Result:** **1.101**
- **Detail:** Freeze-thaw mean=12.79/day, baseline mean=11.61/day

## Detailed findings

### Seasonal calendar pattern

- Peak calendar month (avg daily incidents): **month 2** (13.9/day); trough: **month 5** (10.4/day).
- Winter (Dec–Feb) and summer (Jun–Aug) means come from H1; shoulder seasons sit between those extremes.

### Time-of-day patterns

- Weekday peak hour: **8:00**; weekend peak hour: **16:00**.
- AM rush (7–9 AM) share: **20%** of weekday incidents (H2).
- PM rush (4–6 PM) share: **16%** of weekday incidents (H8).
- Most weekday incidents still fall **outside** both rush windows — disruptions are spread across the service day.

### Disruption duration

- Network median disruption: **2 min**; mean: **5.1 min**.
- Winter median duration: **2 min** vs summer: **2 min**.
- Longest median disruption by line: **Blue** (2 min)

### Primary causes

- **Clientèle**: 54%
- **Équipements fixes**: 17%
- **Matériel roulant**: 14%
- **Exploitation trains**: 8%
- **Autres**: 6%
- Top winter cause: **Clientèle** (61%).
- Top summer cause: **Clientèle** (47%).

### Weather flag comparison

- **H3** (Snow day (D0 or D-1)): **1.115×**
- **H4** (Heavy rain day (≥15 mm)): **1.046×**
- **H5** (Cold snap day (max ≤ -15 °C)): **1.067×**
- **H6** (Freeze-thaw day): **1.101×**
- Strongest weather association in this dataset: **H3** at **1.115×** (association, not causation).

### Dataset snapshot

- Train incidents analyzed (2019+): **29,167**.
- Multi-line events: **1.5%** of train incidents.
- Analysis start filter: **2019-01-01**; incomplete latest month excluded.

### Weather × cause category

- Weather is one reliability factor among several (calendar, operations, passenger behaviour). Lifts below compare **daily cause rates** on flag vs non-flag days.
- **Snow** — strongest lift: **Clientèle** at **1.25×**.
- **Heavy rain** — strongest lift: **Équipements fixes** at **1.18×**.
- **Cold snap** — strongest lift: **Exploitation trains** at **1.165×**.
- **Freeze-thaw** — strongest lift: **Clientèle** at **1.229×**.
- Snow / **Clientèle**: **1.25×** (7.95 vs 6.35/day).
- Snow / **Équipements fixes**: **0.768×** (2.07 vs 2.69/day).
- Snow / **Matériel roulant**: **1.02×** (2.35 vs 2.31/day).
- Snow / **Exploitation trains**: **0.991×** (1.70 vs 1.72/day).
- Heavy rain / **Clientèle**: **0.972×** (6.24 vs 6.42/day).
- Heavy rain / **Équipements fixes**: **1.18×** (3.12 vs 2.65/day).
- Heavy rain / **Matériel roulant**: **1.06×** (2.44 vs 2.30/day).
- Heavy rain / **Exploitation trains**: **0.919×** (1.59 vs 1.73/day).
- Cold snap / **Clientèle**: **0.974×** (6.25 vs 6.41/day).
- Cold snap / **Équipements fixes**: **1.122×** (3.00 vs 2.67/day).
- Cold snap / **Matériel roulant**: **1.115×** (2.57 vs 2.31/day).
- Cold snap / **Exploitation trains**: **1.165×** (2.00 vs 1.72/day).
- Freeze-thaw / **Clientèle**: **1.229×** (7.55 vs 6.14/day).
- Freeze-thaw / **Équipements fixes**: **0.817×** (2.26 vs 2.77/day).
- Freeze-thaw / **Matériel roulant**: **1.153×** (2.59 vs 2.24/day).
- Freeze-thaw / **Exploitation trains**: **0.925×** (1.61 vs 1.74/day).

### Cause trends by year

- Trend window uses complete years **2019–2025** (≥ 300 incident-days per year).
- **Clientèle**: 2,460 → 1,775 incidents (2019→2025, fell); share 52% → 63% (+11%).
- **Équipements fixes**: 656 → 477 incidents (2019→2025, fell); share 14% → 17% (+3%).
- **Matériel roulant**: 957 → 366 incidents (2019→2025, fell); share 20% → 13% (-7%).
- **Exploitation trains**: 667 → 208 incidents (2019→2025, fell); share 14% → 7% (-7%).

### Snow lag analysis

- **D0 (same day)**: **1.086×** (12.81 vs 11.80 incidents/day)
- **D+1 (day after snow)**: **1.134×** (13.36 vs 11.78 incidents/day)
- **D+2 (two days after)**: **1.168×** (13.74 vs 11.76 incidents/day)
- Strongest snow lag effect: **D+2 (two days after)** at **1.168×**.

### Reliability index

- **STM Reliability Score (custom): 72.4/100** — Mean daily score=72.4/100 using **month-stratified** medians (typical ~11 incidents/day, ~41 disruption min/day for the same calendar month).
- Formula: each day scored vs **that month's** median incidents and disruption minutes (2019+ pooled). Daily score = 100 − 50% penalty for excess incidents − 50% penalty for excess disruption minutes (no bonus above 100). Network score = mean daily score.
- Month baselines reduce COVID-era distortion: a busy February is compared to typical Februarys, not a network-wide median pulled down by 2020–2021.
- Best complete year: **2020** (81.3/100); weakest complete year: **2024** (59.1/100).
- Partial year(s) excluded from best/worst ranking: **2025**.

### Simple forecast (exploratory)

- **Next 7 days: ~8.4 incidents/day expected (baseline forecast from recent trend; not a causal model).**
- Method: 28-day rolling mean — not for operational use.

### Holidays and major events

- Quebec statutory holidays: **0.772×** daily incidents (9.19 vs 11.90/day).
- Major Montreal event days: **0.923×** (10.97 vs 11.89/day).
- Holiday share **Clientèle**: 70% vs 58% baseline.
- Holiday share **Équipements fixes**: 16% vs 18% baseline.
- Holiday share **Matériel roulant**: 8% vs 16% baseline.

### Per-event analysis

- Per-event daily incident lift vs all non-event days (curated windows):
- **Nuit Blanche**: **1.056×** (12.50 vs 11.84/day, 6 event-days).
- **Formula 1 Grand Prix**: **0.969×** (11.47 vs 11.84/day, 15 event-days).
- **Montreal Pride**: **0.965×** (11.43 vs 11.85/day, 47 event-days).
- **Jazz Festival**: **0.906×** (10.74 vs 11.86/day, 50 event-days).
- **Osheaga**: **0.77×** (9.13 vs 11.85/day, 15 event-days).

### Canadiens home games

- **Canadiens home game days** (Bell Centre, NHL schedule): **1.080×** daily incidents (12.67 vs 11.74/day, 268 game-days).
- Source: NHL public schedule API (`MTL` home, regular season + playoffs); cached in `data/raw/canadiens_home_games.csv`.
- Game-day share **Clientèle**: 63% vs 58% baseline.
- Game-day share **Équipements fixes**: 15% vs 19% baseline.
- Game-day share **Matériel roulant**: 15% vs 15% baseline.
- Per-line lifts (all four lines, with 95% CI and p-value) are in **Canadiens home-game lift by line** below.

### Duration by weather

- Network median duration — strongest weather association: **Snow** (2 vs 2 min, **1.0×**).
- Snow days — **Clientèle** median **2 min** vs **2 min** baseline (**1.0×**).
- Snow days — **Équipements fixes** median **1 min** vs **1 min** baseline (**1.0×**).
- Snow days — **Matériel roulant** median **3 min** vs **3 min** baseline (**1.0×**).
- Count-based weather lifts and duration lifts can diverge — longer disruptions do not always coincide with more incidents.

### City activity index

- Composite index: weekend (+1) + holiday (+2) + major event (+3). Correlation with daily incidents: **-0.20**.
- High-activity days (index ≥ 3): **10.87** incidents/day vs **12.85** on quiet days (**0.85×**).
- Event windows are curated approximations — see `calendar_enrichment.py`.

### Disruption severity by cause and weather

- **Clientèle**: median **2 min**, mean **4.8 min**.
- **Équipements fixes**: median **1 min**, mean **6.8 min**.
- **Matériel roulant**: median **3 min**, mean **4.4 min**.
- **Exploitation trains**: median **3 min**, mean **3.6 min**.
- Snow days — **Clientèle** median duration **2 min** (+0 min vs overall).
- Snow days — **Équipements fixes** median duration **1 min** (+0 min vs overall).
- Snow days — **Matériel roulant** median duration **3 min** (+0 min vs overall).
- Snow days — **Exploitation trains** median duration **2 min** (-1 min vs overall).

### Clientèle incidents by line

- Single-line train incidents only (multi-line events excluded). **Clientèle** = passenger-related STM cause tag.
- Network-wide Clientèle share: **54%**.
- **Green**: **60%** Clientèle (7,132 of 11,827 incidents).
- **Orange**: **57%** Clientèle (6,576 of 11,506 incidents).
- **Blue**: **35%** Clientèle (1,142 of 3,232 incidents).
- **Yellow**: **28%** Clientèle (592 of 2,153 incidents).

### Snow lift by line

- Snow-or-prev (D0 or D−1) lift on **daily line incident counts** (joined to network-wide YUL weather flags).
- **Green**: **1.165×** (95% CI: 1.07–1.26; p < 0.001) (5.64 vs 4.84/day).
- **Orange**: **1.129×** (95% CI: 1.04–1.23; p = 0.005) (5.37 vs 4.75/day).
- **Blue**: **1.043×** (95% CI: 0.93–1.18; p = 0.471) (2.01 vs 1.93/day).
- **Yellow**: **0.886×** (95% CI: 0.78–1.01; p = 0.291) (1.63 vs 1.84/day).

### Canadiens home-game lift by line

- Bell Centre sits on the **Orange** line (Lucien-L'Allier / Bonaventure corridor). Lifts compare mean **daily line incident counts** on Canadiens home-game dates.
- **Green**: **1.079×** (95% CI: 1.01–1.15; p = 0.033) (5.24 vs 4.86/day).
- **Orange**: **1.102×** (95% CI: 1.03–1.18; p = 0.007) (5.23 vs 4.74/day).
- **Blue**: **1.019×** (95% CI: 0.92–1.12; p = 0.689) (1.96 vs 1.93/day).
- **Yellow**: **0.960×** (95% CI: 0.85–1.09; p = 0.676) (1.76 vs 1.83/day).

### Statistical significance (key lifts)

- Permutation p-values (two-sided, difference in daily means) and **95% bootstrap CIs** for rate ratios on independent day samples. Descriptive — not proof of causation.
- **Network snow (D0 or D−1)**: **1.115×** (95% CI: 1.04–1.19; p < 0.001) (13.10 vs 11.75/day).
- **Winter vs summer (daily counts)**: **1.213×** (95% CI: 1.16–1.27; p < 0.001) (13.26 vs 10.94/day).
- **Snow day — Clientèle (daily cause count)**: **1.250×** (95% CI: 1.13–1.38; p < 0.001) (7.95 vs 6.35/day).
- **Snow day — Équipements fixes (daily cause count)**: **0.768×** (95% CI: 0.63–0.94; p = 0.049) (2.07 vs 2.69/day).
- **Canadiens home game (network)**: **1.080×** (95% CI: 1.02–1.14; p = 0.005) (12.67 vs 11.73/day).
- **Canadiens home — Green line**: **1.079×** (95% CI: 1.01–1.15; p = 0.033) (5.24 vs 4.86/day).
- **Canadiens home — Orange line**: **1.102×** (95% CI: 1.03–1.18; p = 0.007) (5.23 vs 4.74/day).
- **Canadiens home — Blue line**: **1.019×** (95% CI: 0.92–1.12; p = 0.689) (1.96 vs 1.93/day).
- **Canadiens home — Yellow line**: **0.960×** (95% CI: 0.85–1.09; p = 0.676) (1.76 vs 1.83/day).
- **Quebec statutory holiday (network)**: **0.772×** (95% CI: 0.68–0.87; p < 0.001) (9.19 vs 11.90/day).
- **D+2 after snow day (network)**: **1.168×** (95% CI: 1.07–1.26; p < 0.001) (13.74 vs 11.76/day).
- **Snow (D0 or D−1) — Green line**: **1.165×** (95% CI: 1.07–1.26; p < 0.001) (5.64 vs 4.84/day).
- **Snow (D0 or D−1) — Orange line**: **1.129×** (95% CI: 1.04–1.23; p = 0.005) (5.37 vs 4.75/day).
- **Snow (D0 or D−1) — Blue line**: **1.043×** (95% CI: 0.93–1.18; p = 0.471) (2.01 vs 1.93/day).
- **Snow (D0 or D−1) — Yellow line**: **0.886×** (95% CI: 0.78–1.01; p = 0.291) (1.63 vs 1.84/day).

### STM published customer experience

- STM's published **global customer experience index** (positive emoji / 8+ on 10 since 2018) is a **yearly survey metric**, not the same as logged train disruptions.
- Reference series (2019 to 2024): **65%** to **62%** (fell **3** pts).

### Montreal 311 complaint proxy

- Montreal **311** daily **Requete + Plainte** counts are a **city-wide complaint proxy**, not STM satisfaction or metro-specific tickets.
- Analysis window: **2,334,272** complaint-class 311 contacts (**947**/day mean).
- Same-day correlation with metro train incident counts: **r = 0.20** (weak association expected — different populations and definitions).
- Mean daily 311 complaints: **1055** (2019) to **1028** (2025); incident mean **13.9** to **11.2**.

## Methods

- **STM source:** open data train incidents (`Type d'incident = T`) only.
- **Weather source:** Environment Canada daily observations, Montreal Intl A (YUL, station 51157).
- **Join:** `date` (city-wide weather ↔ network-wide incidents).
- **Weather flags:** snow day ≥ 5.0 cm (D0 or D−1 for H3); heavy rain ≥ 15.0 mm; cold snap max temp ≤ -15.0 °C; freeze-thaw when min < 0 and max > 0.
- **Extended STM clock:** hours ≥ 24 folded with `hour % 24` before parsing.

## Data quality

- [PASS] **train_incidents_present** — Train incident share in raw data: 64.0%
- [PASS] **clean_dates** — Rows with null date after clean: 0
- [PASS] **non_negative_duration** — Rows with negative duration_min: 0
- [PASS] **analysis_start_filter** — Rows before 2019-01-01: 0
- [PASS] **unique_weather_dates** — Duplicate weather dates: 0
- [PASS] **weather_dates_present** — Null weather dates: 0

## Charts

- `outputs/monthly_incidents.png`
- `outputs/seasonal_month_profile.png`
- `outputs/weekday_hourly.png`
- `outputs/weekday_weekend_hourly.png`
- `outputs/line_share.png`
- `outputs/yearly_mean_daily.png`
- `outputs/cause_share.png`
- `outputs/duration_by_line.png`
- `outputs/weather_lifts.png`
- `outputs/cause_weather_snow.png`
- `outputs/cause_weather_heatmap.png`
- `outputs/snow_lag_lifts.png`
- `outputs/duration_weather_lifts.png`
- `outputs/cause_trend_yearly.png`
- `outputs/cause_count_trend.png`
- `outputs/reliability_by_year.png`
- `outputs/incident_forecast.png`
- `outputs/calendar_lifts.png`
- `outputs/per_event_lifts.png`
- `outputs/canadiens_home_lift.png`
- `outputs/line_snow_lifts.png`
- `outputs/canadiens_lift_by_line.png`
- `outputs/line_clientele_share.png`
- `outputs/duration_by_cause.png`
- `outputs/experience_vs_reliability.png`
- `outputs/311_vs_incidents.png`

## Limitations
- YUL airport weather is a city-wide proxy, not borough-level.
- STM train incidents only; station incidents (`S`) excluded.
- Multi-line incidents are tagged but not split across lines.
- Weather and calendar patterns are associated with incident counts, not proven causes.
- Per-line weather lifts use daily line counts joined to network-wide weather flags.
- Key lifts include bootstrap 95% CIs and permutation p-values on daily means; independent-day assumption may understate uncertainty when weather persists.
- Reliability score uses month-stratified medians (custom index, not an official STM KPI).
- Dataset may include disruptions shorter than STM's public KPI threshold (~5 minutes).
- 2025 (and the latest month) may be incomplete due to STM monthly refresh lag.
- STM published experience % (reference CSV) is a yearly survey index (bus+métro), not derived from incident logs.
- Montreal 311 counts are city-wide service contacts (Requete + Plainte), not STM-specific rider satisfaction.

## Attribution
- STM open data — Société de transport de Montréal (CC BY 4.0).
- Weather — Environment and Climate Change Canada.
- Montreal 311 — Ville de Montréal open data (donnees.montreal.ca).
