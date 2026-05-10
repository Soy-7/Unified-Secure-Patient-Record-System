"""
routers/hospitals.py — Hospital registry endpoints.

Routes:
  GET /hospitals — list all registered hospitals (no auth required)

No auth is required so that the login page and exchange request form
can populate hospital dropdowns without needing a token first.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import HOSPITALS, get_database
from models.hospital import HospitalResponse

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


@router.get(
    "",
    response_model=list[HospitalResponse],
    summary="List all registered hospitals",
)
async def list_hospitals(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[HospitalResponse]:
    """
    Return all hospitals in the registry.

    No authentication required — used by login/exchange dropdowns.
    In production, you may want to paginate this if the list grows large.
    """
    docs = await db[HOSPITALS].find().to_list(None)
    hospitals = []
    for doc in docs:
        doc.pop("_id", None)
        hospitals.append(HospitalResponse(**doc))
    return hospitals
