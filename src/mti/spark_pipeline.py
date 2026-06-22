"""PySpark transforms for Databricks Delta pipeline."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, IntegerType

from mti.config import (
    COLD_SNAP_MAX_C,
    DELTA_TABLES,
    HEAVY_RAIN_MM,
    SNOW_DAY_CM,
    STM_COLS,
    STM_DELIMITER,
    STM_ENCODING,
    STM_RAW_COLUMNS,
)
from mti.paths import delta_table_path, ensure_dirs, stm_csv_path, weather_csv_path


def _spark_time_col(field: str):
    """Normalize STM time strings for HH:mm parsing."""
    base = F.trim(F.col(field))
    base = F.when(base.isin("#", ""), F.lit(None)).otherwise(base)
    base = F.regexp_replace(base, r"^(\d{1,2}:\d{2}):\d{2}$", r"$1")
    hour = F.regexp_extract(base, r"^(\d{1,2}):", 1).cast("int")
    minute = F.regexp_extract(base, r"^(\d{1,2}):(\d{2})$", 2)
    normalized_hour = hour % 24
    return F.when(
        base.isNull() | hour.isNull() | (minute == ""),
        F.lit(None),
    ).otherwise(F.format_string("%02d:%s", normalized_hour, minute))


def _spark_parse_time(field: str):
    return F.to_timestamp(_spark_time_col(field), "HH:mm")


def rename_stm_raw_columns(df: DataFrame) -> DataFrame:
    """Map French CSV headers to Delta-safe English names by column position."""
    count = len(df.columns)
    names = list(STM_RAW_COLUMNS[:count])
    if count > len(STM_RAW_COLUMNS):
        names.extend(f"extra_{i}" for i in range(count - len(STM_RAW_COLUMNS)))
    return df.toDF(*names)


def read_stm_csv(spark: SparkSession) -> DataFrame:
    df = (
        spark.read.option("header", True)
        .option("sep", STM_DELIMITER)
        .option("encoding", STM_ENCODING)
        .csv(stm_csv_path())
    )
    return rename_stm_raw_columns(df)


def read_weather_csv(spark: SparkSession) -> DataFrame:
    return spark.read.option("header", True).csv(weather_csv_path())


def write_delta(df: DataFrame, key: str, mode: str = "overwrite") -> str:
    layer, name = DELTA_TABLES[key]
    path = delta_table_path(layer, name)
    ensure_dirs()
    df.write.format("delta").mode(mode).save(path)
    return path


def read_delta(spark: SparkSession, key: str) -> DataFrame:
    layer, name = DELTA_TABLES[key]
    return spark.read.format("delta").load(delta_table_path(layer, name))


def ingest_bronze(spark: SparkSession) -> None:
    write_delta(read_stm_csv(spark), "raw_stm")
    write_delta(read_weather_csv(spark), "raw_weather")


def clean_stm(spark: SparkSession) -> DataFrame:
    raw = read_delta(spark, "raw_stm")
    c = STM_COLS

    line_id = (
        F.when(F.col(c["line"]) == "Ligne verte", F.lit(1))
        .when(F.col(c["line"]) == "Ligne orange", F.lit(2))
        .when(F.col(c["line"]) == "Ligne jaune", F.lit(4))
        .when(F.col(c["line"]) == "Ligne bleue", F.lit(5))
        .otherwise(F.lit(None).cast(IntegerType()))
    )
    line_name = (
        F.when(F.col(c["line"]) == "Ligne verte", F.lit("Green"))
        .when(F.col(c["line"]) == "Ligne orange", F.lit("Orange"))
        .when(F.col(c["line"]) == "Ligne jaune", F.lit("Yellow"))
        .when(F.col(c["line"]) == "Ligne bleue", F.lit("Blue"))
        .when(F.col(c["line"]).startswith("Ligne"), F.lit("Multi"))
        .otherwise(F.lit(None))
    )

    start_ts = _spark_parse_time(c["time_start"])
    end_ts = _spark_parse_time(c["time_end"])
    duration_from_clock = (F.unix_timestamp(end_ts) - F.unix_timestamp(start_ts)) / 60.0
    duration_from_clock = F.when(duration_from_clock < 0, duration_from_clock + 24 * 60).otherwise(
        duration_from_clock
    )

    duration_from_bucket = (
        F.when(F.col(c["duration_text"]) == "02 min et moins", F.lit(1.0))
        .when(F.col(c["duration_text"]) == "03 à 04 min", F.lit(3.5))
        .when(F.col(c["duration_text"]) == "05 à 09 min", F.lit(7.0))
        .when(F.col(c["duration_text"]) == "10 à 14 min", F.lit(12.0))
        .when(F.col(c["duration_text"]) == "15 à 19 min", F.lit(17.0))
        .when(F.col(c["duration_text"]) == "20 à 24 min", F.lit(22.0))
        .when(F.col(c["duration_text"]) == "25 à 29 min", F.lit(27.0))
        .when(F.col(c["duration_text"]) == "30 min et plus", F.lit(35.0))
        .otherwise(F.lit(None).cast(DoubleType()))
    )

    incident_id_col = F.regexp_replace(F.col(c["incident_id"]), "^\ufeff", "")

    cleaned = (
        raw.filter(F.col(c["incident_type"]) == "T")
        .withColumn("incident_id", incident_id_col)
        .withColumn("date", F.to_date(F.col(c["calendar_date"])))
        .withColumn("hour", F.hour(_spark_parse_time(c["time_start"])))
        .withColumn("dow", F.dayofweek(F.col("date")))
        .withColumn("is_weekday", F.dayofweek(F.col("date")).between(2, 6))
        .withColumn("line_id", line_id)
        .withColumn("line_name", line_name)
        .withColumn("line_raw", F.col(c["line"]))
        .withColumn(
            "is_multi_line",
            F.col("line_id").isNull() & F.col(c["line"]).startswith("Ligne"),
        )
        .withColumn(
            "duration_min",
            F.coalesce(duration_from_clock.cast(DoubleType()), duration_from_bucket),
        )
        .withColumn("cause_primary", F.col(c["cause_primary"]))
        .withColumn("symptom", F.col(c["symptom"]))
        .withColumn("duration_text", F.col(c["duration_text"]))
        .filter(F.col("date") >= F.lit("2019-01-01").cast(DateType()))
        .select(
            "incident_id",
            "date",
            "hour",
            "dow",
            "is_weekday",
            "line_id",
            "line_name",
            "line_raw",
            "is_multi_line",
            "duration_min",
            "cause_primary",
            "symptom",
            "duration_text",
        )
    )
    write_delta(cleaned, "clean_stm")
    return cleaned


def clean_weather(spark: SparkSession) -> DataFrame:
    raw = read_delta(spark, "raw_weather")
    cleaned = (
        raw.withColumn("date", F.to_date(F.col("date")))
        .withColumn("max_temp_c", F.col("max_temp_c").cast(DoubleType()))
        .withColumn("min_temp_c", F.col("min_temp_c").cast(DoubleType()))
        .withColumn("total_precip_mm", F.coalesce(F.col("total_precip_mm").cast(DoubleType()), F.lit(0.0)))
        .withColumn("total_snow_cm", F.coalesce(F.col("total_snow_cm").cast(DoubleType()), F.lit(0.0)))
        .withColumn("snow_on_ground_cm", F.col("snow_on_ground_cm").cast(DoubleType()))
        .withColumn("snow_day_flag", F.col("total_snow_cm") >= F.lit(SNOW_DAY_CM))
        .withColumn("heavy_rain_flag", F.col("total_precip_mm") >= F.lit(HEAVY_RAIN_MM))
        .withColumn("cold_snap_flag", F.col("max_temp_c") <= F.lit(COLD_SNAP_MAX_C))
        .withColumn(
            "freeze_thaw_flag",
            (F.col("min_temp_c") < 0) & (F.col("max_temp_c") > 0),
        )
        .dropDuplicates(["date"])
    )
    write_delta(cleaned, "clean_weather")
    return cleaned


def build_gold_facts(spark: SparkSession) -> None:
    incidents = read_delta(spark, "clean_stm")
    weather = read_delta(spark, "clean_weather")

    fact_daily = incidents.groupBy("date").agg(
        F.count("*").alias("incident_count"),
        F.sum("duration_min").alias("total_disruption_min"),
    )
    write_delta(fact_daily, "fact_daily")

    fact_by_line = (
        incidents.filter(F.col("line_id").isNotNull())
        .groupBy("date", "line_id", "line_name")
        .agg(
            F.count("*").alias("incident_count"),
            F.sum("duration_min").alias("disruption_min"),
        )
    )
    write_delta(fact_by_line, "fact_by_line")

    fact_weather = weather.select(
        "date",
        "max_temp_c",
        "min_temp_c",
        "total_precip_mm",
        "total_snow_cm",
        "snow_on_ground_cm",
        "snow_day_flag",
        "heavy_rain_flag",
        "cold_snap_flag",
        "freeze_thaw_flag",
    )
    write_delta(fact_weather, "fact_weather")

    joined = fact_daily.join(fact_weather, on="date", how="left")
    write_delta(joined, "fact_joined")


def run_full_spark_pipeline(spark: SparkSession) -> None:
    ingest_bronze(spark)
    clean_stm(spark)
    clean_weather(spark)
    build_gold_facts(spark)
