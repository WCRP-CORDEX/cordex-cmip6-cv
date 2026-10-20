import json
import re
import unicodedata
from pathlib import Path

import geonamescache
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim


def unpack_location(location):
    entries = location.strip().rstrip("]").split(",")
    try:
        city, country = entries[-2].strip(), entries[-1].strip()
    except IndexError:
        raise ValueError(
            f"Location string '{location}' does not contain enough entries to unpack city and country."
        )
    # e.g. "C. A. Buenos Aires (CABA)" -> "Buenos Aires"
    city = re.sub(r"\(.*?\)", "", city)
    city = re.sub(r"^C\.\s*A\.\s*", "", city).strip()
    return city, country


def _norm(text):
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).strip().lower()


COUNTRY_ALIASES = {
    "uk": "gb",
    "united kingdom": "gb",
    "great britain": "gb",
    "england": "gb",
    "usa": "us",
    "united states of america": "us",
    "united states": "us",
    "the netherlands": "nl",
    "czech republic": "cz",
    "russia": "ru",
}

_gc = geonamescache.GeonamesCache()
_country_codes = {_norm(c["name"]): code for code, c in _gc.get_countries().items()}
_country_codes.update(COUNTRY_ALIASES)

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = REPO_ROOT / "institution-coordinates-cache.json"
_cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}

_cities_by_name = None


def _get_cities_index():
    # Built lazily: only needed when a city is not in the cache
    global _cities_by_name
    if _cities_by_name is None:
        _cities_by_name = {}
        for city in _gc.get_cities().values():
            for name in [city["name"], *city.get("alternatenames", [])]:
                if name:
                    _cities_by_name.setdefault(_norm(name), []).append(city)
    return _cities_by_name


_geocode = None


def _nominatim(location):
    # Online fallback, only created when the offline lookup fails
    global _geocode
    if _geocode is None:
        geolocator = Nominatim(user_agent="cordex-cmip6-cv-institution-map", timeout=10)
        _geocode = RateLimiter(
            geolocator.geocode,
            min_delay_seconds=1.1,
            max_retries=3,
            error_wait_seconds=5.0,
            swallow_exceptions=True,
        )
    loc = _geocode(location)
    return (loc.latitude, loc.longitude) if loc else (None, None)


def _lookup_city(city, country_code=None):
    candidates = _get_cities_index().get(_norm(city), [])
    if country_code:
        candidates = [c for c in candidates if c["countrycode"].lower() == country_code]
    if not candidates:
        return None
    best = max(candidates, key=lambda c: c["population"])
    return best["latitude"], best["longitude"]


def get_city_coordinates(city, country):
    key = f"{city}, {country}"
    if key not in _cache:
        coords = _lookup_city(city, _country_codes.get(_norm(country))) or _nominatim(
            key
        )
        if coords == (None, None):
            return coords
        _cache[key] = list(coords)
        CACHE_FILE.write_text(json.dumps(_cache, indent=2, ensure_ascii=False))
    return tuple(_cache[key])


def main():
    with open(REPO_ROOT / "CORDEX-CMIP6_institution_id.json", "r") as file:
        data = json.load(file)

    cities = []
    countries = set()

    for locations in data["institution_id"].values():
        for location in locations.split(";"):
            city, country = unpack_location(location)
            countries.add(country)
            city_coords = get_city_coordinates(city, country)
            if city_coords != (None, None):
                cities.append(
                    {
                        "name": city,
                        "latitude": city_coords[0],
                        "longitude": city_coords[1],
                    }
                )

    city_df = pd.DataFrame(cities)
    city_gdf = gpd.GeoDataFrame(
        city_df,
        geometry=gpd.points_from_xy(city_df["longitude"], city_df["latitude"]),
        crs="EPSG:4326",
    )

    world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres")).to_crs(
        "EPSG:4326"
    )

    # Natural Earth has iso_a3 == -99 for some countries (e.g. France, Norway), so also match by name
    iso2_codes = {_country_codes.get(_norm(c)) for c in countries} - {None}
    iso3_codes = {
        info["iso3"]
        for code, info in _gc.get_countries().items()
        if code.lower() in iso2_codes
    }
    names = {_norm(c) for c in countries}
    is_highlighted = world["iso_a3"].isin(iso3_codes) | world["name"].map(_norm).isin(
        names
    )
    highlighted = world[is_highlighted]

    robinson = "+proj=robin"
    fig, ax = plt.subplots(figsize=(15, 10))
    world.to_crs(robinson).plot(
        ax=ax, color="#8dc2be", edgecolor="white", linewidth=0.6
    )
    highlighted.to_crs(robinson).plot(
        ax=ax, color="#209790", edgecolor="white", linewidth=0.6
    )
    city_gdf.to_crs(robinson).plot(
        ax=ax,
        color="#ffc941",
        marker=".",
        markersize=55,
        edgecolor="#209790",
        linewidth=0.3,
    )
    ax.set_axis_off()

    # ax.legend(handles=[
    #    Patch(facecolor='#209790', label='Countries contributing to CORDEX-CMIP6'),
    #    Line2D([], [], color='#ffc941', marker='.', linestyle='', label='Institutions'),
    # ], loc='lower left')

    ax.set_title("Modelling centers contributing to CORDEX-CMIP6", fontsize=14, pad=20)
    fig.savefig(
        REPO_ROOT / "docs" / "institution-map.svg", format="svg", bbox_inches="tight"
    )
    plt.show()


if __name__ == "__main__":
    main()
