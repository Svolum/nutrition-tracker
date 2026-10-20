from datetime import date
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.domain import (
    ActivityLevel,
    Gender,
    GoalType,
    NutritionDomainService,
    quantize_dec,
)

NonNegativeMacro = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("100"), allow_inf_nan=False),
]


class ProductUnitCreate(BaseModel):
    unit_name: str = Field(..., min_length=1, max_length=80, description="Название меры (шт, стакан, пачка)")
    grams_per_unit: Decimal = Field(
        ..., gt=Decimal("0"), le=Decimal("5000"), allow_inf_nan=False, description="Вес 1 единицы в граммах"
    )


class ProductUnitRead(ProductUnitCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    calories_100g: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("900"), allow_inf_nan=False
    )
    proteins_100g: NonNegativeMacro
    fats_100g: NonNegativeMacro
    carbs_100g: NonNegativeMacro
    fiber_100g: NonNegativeMacro = Decimal("0.00")
    units: list[ProductUnitCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_physical_dry_weight(self) -> "ProductCreate":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Название продукта не может состоять только из пробелов.")

        dry_sum = (
            self.proteins_100g
            + self.fats_100g
            + self.carbs_100g
            + self.fiber_100g
        )
        if dry_sum > Decimal("100.00"):
            raise ValueError(
                f"Физическая ошибка: сумма Б ({self.proteins_100g}г) + Ж ({self.fats_100g}г) + "
                f"У ({self.carbs_100g}г) + Клетчатка ({self.fiber_100g}г) = {dry_sum}г, "
                f"что превышает 100 г на 100 г продукта."
            )
        return self


class ProductRead(BaseModel):
    id: int
    name: str
    calories_100g: Decimal
    proteins_100g: Decimal
    fats_100g: Decimal
    carbs_100g: Decimal
    fiber_100g: Decimal
    units: list[ProductUnitRead]

    @computed_field
    @property
    def atwater_calories_100g(self) -> Decimal:
        return NutritionDomainService.calculate_atwater_calories(
            self.proteins_100g, self.fats_100g, self.carbs_100g
        )

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    gender: Gender = Gender.MALE
    age: int = Field(default=22, ge=10, le=120)
    weight_kg: Decimal = Field(
        default=Decimal("75.00"), gt=Decimal("20"), le=Decimal("350"), allow_inf_nan=False
    )
    height_cm: Decimal = Field(
        default=Decimal("180.00"), gt=Decimal("80"), le=Decimal("260"), allow_inf_nan=False
    )
    activity_level: ActivityLevel = ActivityLevel.MODERATE
    goal: GoalType = GoalType.MAINTENANCE

    use_manual_targets: bool = False
    manual_calories: Decimal = Field(
        default=Decimal("2500.00"), ge=Decimal("500"), le=Decimal("15000"), allow_inf_nan=False
    )
    manual_proteins: Decimal = Field(
        default=Decimal("140.00"), ge=Decimal("0"), le=Decimal("1000"), allow_inf_nan=False
    )
    manual_fats: Decimal = Field(
        default=Decimal("80.00"), ge=Decimal("0"), le=Decimal("1000"), allow_inf_nan=False
    )
    manual_carbs: Decimal = Field(
        default=Decimal("300.00"), ge=Decimal("0"), le=Decimal("2000"), allow_inf_nan=False
    )
    manual_fiber: Decimal = Field(
        default=Decimal("30.00"), ge=Decimal("0"), le=Decimal("300"), allow_inf_nan=False
    )


class ProfileRead(ProfileUpdate):
    recommended_bmr: Decimal
    recommended_tdee: Decimal
    active_target_calories: Decimal
    active_target_proteins: Decimal
    active_target_fats: Decimal
    active_target_carbs: Decimal
    active_target_fiber: Decimal


class LogEntryCreate(BaseModel):
    log_date: date
    product_id: int = Field(..., gt=0)
    unit_id: int | None = Field(
        default=None,
        description="ID штучной меры из ProductUnit. Если None — ввод напрямую в граммах.",
    )
    quantity: Decimal = Field(
        ..., gt=Decimal("0"), le=Decimal("10000"), allow_inf_nan=False
    )


class MacroSummaryDTO(BaseModel):
    declared_calories: Decimal
    atwater_calories: Decimal
    calorie_delta: Decimal
    proteins: Decimal
    fats: Decimal
    carbs: Decimal
    fiber: Decimal


class LogEntryRead(BaseModel):
    id: int
    log_date: date
    product_id: int
    product_name: str
    unit_label: str
    quantity: Decimal
    total_grams: Decimal
    macros: MacroSummaryDTO


class DailyPotResponse(BaseModel):
    log_date: date
    entries: list[LogEntryRead]
    totals: MacroSummaryDTO
    targets: ProfileRead
    remaining_declared_calories: Decimal
    remaining_proteins: Decimal
    remaining_fats: Decimal
    remaining_carbs: Decimal
    remaining_fiber: Decimal