"""On-demand Google Places search. Coordinates and results are not persisted."""
from math import asin, cos, radians, sin, sqrt
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend import settings

SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.googleMapsUri", "places.businessStatus",
    "places.nationalPhoneNumber", "places.internationalPhoneNumber",
    "places.attributions",
])
SERVICE_TYPES = {"mechanic": ["car_repair"], "tyres": ["tire_shop"]}


class NearbySearch(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_metres: int = Field(default=5000, ge=1, le=50000)
    service: Literal["mechanic", "tyres"] = "mechanic"


class Coordinates(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DisplayName(BaseModel):
    text: str = ""


class Attribution(BaseModel):
    provider: str = ""
    providerUri: str = ""


class GooglePlace(BaseModel):
    id: str = Field(min_length=1)
    displayName: DisplayName = Field(default_factory=DisplayName)
    formattedAddress: str = ""
    location: Coordinates
    googleMapsUri: str = ""
    businessStatus: str = ""
    nationalPhoneNumber: str = ""
    internationalPhoneNumber: str = ""
    attributions: list[Attribution] = Field(default_factory=list)


class GoogleResults(BaseModel):
    places: list[GooglePlace] = Field(default_factory=list, max_length=20)


def distance_metres(latitude, longitude, location):
    lat_difference = radians(location.latitude - latitude)
    lon_difference = radians(location.longitude - longitude)
    value = (sin(lat_difference / 2) ** 2
             + cos(radians(latitude)) * cos(radians(location.latitude))
             * sin(lon_difference / 2) ** 2)
    return round(6371000 * 2 * asin(sqrt(min(1, max(0, value)))))


async def search(request: NearbySearch):
    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(503, "Nearby assistance is not configured yet. Use your saved roadside contacts or search in Google Maps.")
    body = {
        "includedTypes": SERVICE_TYPES[request.service],
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
        "languageCode": "en",
        "regionCode": "MY",
        "locationRestriction": {"circle": {
            "center": {"latitude": request.latitude, "longitude": request.longitude},
            "radius": request.radius_metres,
        }},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.GOOGLE_PLACES_TIMEOUT, follow_redirects=False) as client:
            response = await client.post(SEARCH_URL, json=body, headers={
                "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": FIELD_MASK,
            })
        if response.status_code == 429:
            raise HTTPException(503, "Nearby search is busy or its quota has been reached. Try again later or search in Google Maps.")
        response.raise_for_status()
        results = GoogleResults.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError):
        # Never expose Google's response body, request headers or API key.
        raise HTTPException(503, "Nearby assistance could not be reached. Check your connection and retry, or search in Google Maps.") from None
    return {"places": [
        {
            "id": place.id,
            "name": place.displayName.text or "Unnamed business",
            "address": place.formattedAddress,
            "phone": place.internationalPhoneNumber or place.nationalPhoneNumber,
            "maps_url": place.googleMapsUri,
            "business_status": place.businessStatus,
            "distance_metres": distance_metres(request.latitude, request.longitude, place.location),
            "attributions": [item.model_dump() for item in place.attributions],
        }
        for place in results.places
        if place.businessStatus != "CLOSED_PERMANENTLY"
    ]}
