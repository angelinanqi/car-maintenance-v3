"""Guest-accessible online assistance, independent of accounts and AI."""
from collections import deque
from time import monotonic

from fastapi import APIRouter, HTTPException, Request

from backend.services import places

router = APIRouter(prefix="/emergency", tags=["Emergency"])
# Process-local guard for this paid public endpoint. Also configure Cloud quotas
# and a shared gateway limiter when deploying multiple backend workers.
_requests = deque()


def limit_searches(request: Request):
    now = monotonic()
    while _requests and _requests[0][0] <= now - 60:
        _requests.popleft()
    address = request.client.host if request.client else "unknown"
    if len(_requests) >= 60 or sum(ip == address for _, ip in _requests) >= 10:
        raise HTTPException(429, "Too many nearby searches. Wait a minute before trying again.", headers={"Retry-After": "60"})
    _requests.append((now, address))


@router.post("/nearby")
async def nearby_search(body: places.NearbySearch, request: Request):
    limit_searches(request)
    return await places.search(body)
