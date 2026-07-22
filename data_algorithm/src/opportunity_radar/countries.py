from __future__ import annotations


TARGET_COUNTRIES = {
    "VNM": {
        "iso2": "VN",
        "name_ko": "베트남",
        "name_en": "Vietnam",
        "region_code": "SEA",
        "aliases": ("베트남", "Vietnam"),
    },
    "IDN": {
        "iso2": "ID",
        "name_ko": "인도네시아",
        "name_en": "Indonesia",
        "region_code": "SEA",
        "aliases": ("인도네시아", "Indonesia"),
    },
    "MNG": {
        "iso2": "MN",
        "name_ko": "몽골",
        "name_en": "Mongolia",
        "region_code": "NEA",
        "aliases": ("몽골", "Mongolia"),
    },
}


ISO2_TO_ISO3 = {cfg["iso2"]: iso3 for iso3, cfg in TARGET_COUNTRIES.items()}


def upsert_target_countries(conn) -> None:
    for iso3, cfg in TARGET_COUNTRIES.items():
        conn.execute(
            """INSERT INTO country(iso3, iso2, name_ko, name_en, region_code)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(iso3) DO UPDATE SET iso2=excluded.iso2,
                 name_ko=excluded.name_ko, name_en=excluded.name_en,
                 region_code=excluded.region_code""",
            (iso3, cfg["iso2"], cfg["name_ko"], cfg["name_en"], cfg["region_code"]),
        )
