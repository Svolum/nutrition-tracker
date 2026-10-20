from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import (
    ActivityLevel,
    Gender,
    GoalType,
    MacroBreakdown,
    NutritionDomainService,
    quantize_dec,
)
from app.models import DailyLogEntry, Product, ProductUnit, UserProfile
from app.schemas import (
    DailyPotResponse,
    LogEntryCreate,
    LogEntryRead,
    MacroSummaryDTO,
    ProductCreate,
    ProfileRead,
    ProfileUpdate,
)


INITIAL_PRODUCTS: list[dict] = [
    {
        "name": "Арахис жареный несоленый",
        "calories_100g": Decimal("585.00"),
        "proteins_100g": Decimal("25.00"),
        "fats_100g": Decimal("50.00"),
        "carbs_100g": Decimal("16.67"),
        "fiber_100g": Decimal("8.00"),
        "units": [
            {"unit_name": "Горсть (30 г)", "grams_per_unit": Decimal("30.00")},
            {"unit_name": "Пачка (300 г)", "grams_per_unit": Decimal("300.00")},
        ],
    },
    {
        "name": "Гречневая крупа (ядрица, сухая)",
        "calories_100g": Decimal("313.00"),
        "proteins_100g": Decimal("12.60"),
        "fats_100g": Decimal("3.30"),
        "carbs_100g": Decimal("62.10"),
        "fiber_100g": Decimal("11.30"),
        "units": [
            {"unit_name": "Стакан 250 мл (210 г)", "grams_per_unit": Decimal("210.00")},
            {"unit_name": "Стандартная порция сухой (80 г)", "grams_per_unit": Decimal("80.00")},
        ],
    },
    {
        "name": "Фарш говяжий (домашний)",
        "calories_100g": Decimal("254.00"),
        "proteins_100g": Decimal("17.20"),
        "fats_100g": Decimal("20.00"),
        "carbs_100g": Decimal("0.00"),
        "fiber_100g": Decimal("0.00"),
        "units": [
            {"unit_name": "Порция (150 г)", "grams_per_unit": Decimal("150.00")},
            {"unit_name": "Упаковка (400 г)", "grams_per_unit": Decimal("400.00")},
        ],
    },
    {
        "name": "Филе куриной грудки (сырое)",
        "calories_100g": Decimal("113.00"),
        "proteins_100g": Decimal("23.60"),
        "fats_100g": Decimal("1.90"),
        "carbs_100g": Decimal("0.40"),
        "fiber_100g": Decimal("0.00"),
        "units": [
            {"unit_name": "Малое филе (180 г)", "grams_per_unit": Decimal("180.00")},
            {"unit_name": "Крупное филе (250 г)", "grams_per_unit": Decimal("250.00")},
        ],
    },
    {
        "name": "Яйцо куриное С1",
        "calories_100g": Decimal("157.00"),
        "proteins_100g": Decimal("12.70"),
        "fats_100g": Decimal("11.50"),
        "carbs_100g": Decimal("0.70"),
        "fiber_100g": Decimal("0.00"),
        "units": [
            {"unit_name": "Штука С1 (55 г)", "grams_per_unit": Decimal("55.00")},
            {"unit_name": "Штука С0 (65 г)", "grams_per_unit": Decimal("65.00")},
        ],
    },
    {
        "name": "Кукуруза сахарная консервированная",
        "calories_100g": Decimal("58.00"),
        "proteins_100g": Decimal("2.20"),
        "fats_100g": Decimal("0.40"),
        "carbs_100g": Decimal("11.20"),
        "fiber_100g": Decimal("2.00"),
        "units": [
            {"unit_name": "Столовая ложка (25 г)", "grams_per_unit": Decimal("25.00")},
            {"unit_name": "Банка без жидкости (280 г)", "grams_per_unit": Decimal("280.00")},
        ],
    },
    {
        "name": "Морковь свежая",
        "calories_100g": Decimal("41.00"),
        "proteins_100g": Decimal("0.90"),
        "fats_100g": Decimal("0.20"),
        "carbs_100g": Decimal("6.80"),
        "fiber_100g": Decimal("2.80"),
        "units": [
            {"unit_name": "Средний корнеплод (100 г)", "grams_per_unit": Decimal("100.00")},
        ],
    },
    {
        "name": "Лук репчатый",
        "calories_100g": Decimal("40.00"),
        "proteins_100g": Decimal("1.10"),
        "fats_100g": Decimal("0.10"),
        "carbs_100g": Decimal("8.20"),
        "fiber_100g": Decimal("1.70"),
        "units": [
            {"unit_name": "Средняя луковица (85 г)", "grams_per_unit": Decimal("85.00")},
        ],
    },
    {
        "name": "Томатная паста (25% сухих веществ)",
        "calories_100g": Decimal("82.00"),
        "proteins_100g": Decimal("4.30"),
        "fats_100g": Decimal("0.50"),
        "carbs_100g": Decimal("15.80"),
        "fiber_100g": Decimal("4.10"),
        "units": [
            {"unit_name": "Столовая ложка (30 г)", "grams_per_unit": Decimal("30.00")},
        ],
    },
    {
        "name": "Овсяные хлопья Геркулес",
        "calories_100g": Decimal("352.00"),
        "proteins_100g": Decimal("12.30"),
        "fats_100g": Decimal("6.20"),
        "carbs_100g": Decimal("61.80"),
        "fiber_100g": Decimal("6.00"),
        "units": [
            {"unit_name": "Стакан 250 мл (90 г)", "grams_per_unit": Decimal("90.00")},
            {"unit_name": "Столовая ложка (15 г)", "grams_per_unit": Decimal("15.00")},
        ],
    },
]


async def seed_initial_data(session: AsyncSession) -> None:
    """Идемпотентное заполнение справочника продуктов и профиля по умолчанию."""
    existing_product = await session.scalar(select(Product.id).limit(1))
    if existing_product is None:
        for item in INITIAL_PRODUCTS:
            units_data = item.get("units", [])
            product = Product(
                name=item["name"],
                calories_100g=item["calories_100g"],
                proteins_100g=item["proteins_100g"],
                fats_100g=item["fats_100g"],
                carbs_100g=item["carbs_100g"],
                fiber_100g=item["fiber_100g"],
                units=[
                    ProductUnit(
                        unit_name=u["unit_name"],
                        grams_per_unit=u["grams_per_unit"],
                    )
                    for u in units_data
                ],
            )
            session.add(product)

    existing_profile = await session.get(UserProfile, 1)
    if existing_profile is None:
        session.add(UserProfile(id=1))

    await session.commit()


class NutritionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_products(self) -> list[Product]:
        stmt = select(Product).order_by(Product.name.asc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def create_product(self, payload: ProductCreate) -> Product:
        existing = await self.session.scalar(
            select(Product).where(Product.name.ilike(payload.name))
        )
        if existing is not None:
            raise ValueError(f"Продукт «{payload.name}» уже существует в справочнике.")

        product = Product(
            name=payload.name,
            calories_100g=payload.calories_100g,
            proteins_100g=payload.proteins_100g,
            fats_100g=payload.fats_100g,
            carbs_100g=payload.carbs_100g,
            fiber_100g=payload.fiber_100g,
            units=[
                ProductUnit(unit_name=u.unit_name.strip(), grams_per_unit=u.grams_per_unit)
                for u in payload.units
            ],
        )
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def get_profile_dto(self) -> ProfileRead:
        profile = await self.session.get(UserProfile, 1)
        if profile is None:
            profile = UserProfile(id=1)
            self.session.add(profile)
            await self.session.commit()
            await self.session.refresh(profile)

        rec = NutritionDomainService.calculate_recommended_targets(
            gender=Gender(profile.gender),
            age=profile.age,
            weight_kg=profile.weight_kg,
            height_cm=profile.height_cm,
            activity_level=ActivityLevel(profile.activity_level),
            goal=GoalType(profile.goal),
        )

        is_manual = profile.use_manual_targets
        return ProfileRead(
            gender=Gender(profile.gender),
            age=profile.age,
            weight_kg=profile.weight_kg,
            height_cm=profile.height_cm,
            activity_level=ActivityLevel(profile.activity_level),
            goal=GoalType(profile.goal),
            use_manual_targets=is_manual,
            manual_calories=profile.manual_calories,
            manual_proteins=profile.manual_proteins,
            manual_fats=profile.manual_fats,
            manual_carbs=profile.manual_carbs,
            manual_fiber=profile.manual_fiber,
            recommended_bmr=rec.bmr,
            recommended_tdee=rec.tdee,
            active_target_calories=profile.manual_calories if is_manual else rec.target_calories,
            active_target_proteins=profile.manual_proteins if is_manual else rec.target_proteins,
            active_target_fats=profile.manual_fats if is_manual else rec.target_fats,
            active_target_carbs=profile.manual_carbs if is_manual else rec.target_carbs,
            active_target_fiber=profile.manual_fiber if is_manual else rec.target_fiber,
        )

    async def update_profile(self, payload: ProfileUpdate) -> ProfileRead:
        profile = await self.session.get(UserProfile, 1)
        if profile is None:
            profile = UserProfile(id=1)
            self.session.add(profile)

        for field_name, val in payload.model_dump().items():
            setattr(profile, field_name, val.value if hasattr(val, "value") else val)

        await self.session.commit()
        return await self.get_profile_dto()

    async def add_log_entry(self, payload: LogEntryCreate) -> DailyLogEntry:
        product = await self.session.get(Product, payload.product_id)
        if product is None:
            raise ValueError(f"Продукт с ID={payload.product_id} не найден.")

        unit_label = "г"
        total_grams = quantize_dec(payload.quantity)

        if payload.unit_id is not None:
            matched_unit = next((u for u in product.units if u.id == payload.unit_id), None)
            if matched_unit is None:
                raise ValueError("Указанная штучная мера не принадлежит выбранному продукту.")
            unit_label = matched_unit.unit_name
            total_grams = quantize_dec(payload.quantity * matched_unit.grams_per_unit)

        if total_grams > Decimal("20000.00"):
            raise ValueError("Суммарный вес одной записи не может превышать 20 кг (20000 г).")

        entry = DailyLogEntry(
            log_date=payload.log_date,
            product_id=product.id,
            unit_label=unit_label,
            quantity=quantize_dec(payload.quantity),
            total_grams=total_grams,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def delete_log_entry(self, entry_id: int) -> bool:
        entry = await self.session.get(DailyLogEntry, entry_id)
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def get_daily_pot(self, target_date: date) -> DailyPotResponse:
        stmt = (
            select(DailyLogEntry)
            .where(DailyLogEntry.log_date == target_date)
            .order_by(DailyLogEntry.created_at.asc(), DailyLogEntry.id.asc())
        )
        entries = list((await self.session.scalars(stmt)).all())

        entry_dtos: list[LogEntryRead] = []
        breakdowns: list[MacroBreakdown] = []

        for e in entries:
            p = e.product
            b = NutritionDomainService.calculate_portion_macros(
                calories_100g=p.calories_100g,
                proteins_100g=p.proteins_100g,
                fats_100g=p.fats_100g,
                carbs_100g=p.carbs_100g,
                fiber_100g=p.fiber_100g,
                grams=e.total_grams,
            )
            breakdowns.append(b)
            entry_dtos.append(
                LogEntryRead(
                    id=e.id,
                    log_date=e.log_date,
                    product_id=p.id,
                    product_name=p.name,
                    unit_label=e.unit_label,
                    quantity=e.quantity,
                    total_grams=e.total_grams,
                    macros=MacroSummaryDTO(
                        declared_calories=b.declared_calories,
                        atwater_calories=b.atwater_calories,
                        calorie_delta=b.calorie_delta,
                        proteins=b.proteins,
                        fats=b.fats,
                        carbs=b.carbs,
                        fiber=b.fiber,
                    ),
                )
            )

        agg = NutritionDomainService.aggregate_macros(breakdowns)
        targets = await self.get_profile_dto()

        return DailyPotResponse(
            log_date=target_date,
            entries=entry_dtos,
            totals=MacroSummaryDTO(
                declared_calories=agg.declared_calories,
                atwater_calories=agg.atwater_calories,
                calorie_delta=agg.calorie_delta,
                proteins=agg.proteins,
                fats=agg.fats,
                carbs=agg.carbs,
                fiber=agg.fiber,
            ),
            targets=targets,
            remaining_declared_calories=quantize_dec(
                targets.active_target_calories - agg.declared_calories
            ),
            remaining_proteins=quantize_dec(targets.active_target_proteins - agg.proteins),
            remaining_fats=quantize_dec(targets.active_target_fats - agg.fats),
            remaining_carbs=quantize_dec(targets.active_target_carbs - agg.carbs),
            remaining_fiber=quantize_dec(targets.active_target_fiber - agg.fiber),
        )