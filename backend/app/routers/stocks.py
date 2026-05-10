from fastapi import APIRouter, HTTPException

from app.services.ls_api import client

router = APIRouter(prefix="/api")


@router.get("/stocks")
def get_stocks():
    try:
        return client.get_bic_stocks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
