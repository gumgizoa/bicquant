from fastapi import APIRouter, HTTPException

from app.services.ls_api import get_bic_stocks

router = APIRouter(prefix="/api")


@router.get("/stocks")
async def get_stocks():
    try:
        return await get_bic_stocks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
