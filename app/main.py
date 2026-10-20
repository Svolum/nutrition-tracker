from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, Base, engine, get_db
from app.repositories import NutritionRepository, seed_initial_data
from app.schemas import (
    DailyPotResponse,
    LogEntryCreate,
    ProductCreate,
    ProductRead,
    ProfileRead,
    ProfileUpdate,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
    yield
    await engine.dispose()


app = FastAPI(
    title="Daily Nutrition & Macro Calculator API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    )
    return response


def get_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> NutritionRepository:
    return NutritionRepository(session)


@app.get("/", include_in_schema=False)
async def serve_spa() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/products", response_model=list[ProductRead])
async def list_products(
    repo: Annotated[NutritionRepository, Depends(get_repo)],
) -> list[ProductRead]:
    products = await repo.list_products()
    return [ProductRead.model_validate(p) for p in products]


@app.post("/api/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    repo: Annotated[NutritionRepository, Depends(get_repo)],
) -> ProductRead:
    try:
        product = await repo.create_product(payload)
        return ProductRead.model_validate(product)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/api/profile", response_model=ProfileRead)
async def get_profile(
    repo: Annotated[NutritionRepository, Depends(get_repo)],
) -> ProfileRead:
    return await repo.get_profile_dto()


@app.put("/api/profile", response_model=ProfileRead)
async def update_profile(
    payload: ProfileUpdate,
    repo: Annotated[NutritionRepository, Depends(get_repo)],
) -> ProfileRead:
    return await repo.update_profile(payload)


@app.get("/api/daily-pot", response_model=DailyPotResponse)
async def get_daily_pot(
    repo: Annotated[NutritionRepository, Depends(get_repo)],
    log_date: Annotated[date, Query(description="Дата дневного котла (YYYY-MM-DD)")] = date.today(),
) -> DailyPotResponse:
    return await repo.get_daily_pot(log_date)


@app.post("/api/daily-pot/entries", response_model=DailyPotResponse, status_code=status.HTTP_201_CREATED)
async def add_entry_to_pot(
    payload: LogEntryCreate,
    repo: Annotated[NutritionRepository, Depends(get_repo)],
) -> DailyPotResponse:
    try:
        await repo.add_log_entry(payload)
        return await repo.get_daily_pot(payload.log_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.delete("/api/daily-pot/entries/{entry_id}", response_model=DailyPotResponse)
async def remove_entry_from_pot(
    entry_id: int,
    repo: Annotated[NutritionRepository, Depends(get_repo)],
    log_date: Annotated[date, Query()] = date.today(),
) -> DailyPotResponse:
    deleted = await repo.delete_log_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена.")
    return await repo.get_daily_pot(log_date)