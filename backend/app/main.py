from fastapi import FastAPI

from app.routers.stocks import router as stocks_router

app = FastAPI()
app.include_router(stocks_router)
