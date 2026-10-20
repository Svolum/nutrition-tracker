from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

TWO_PLACES = Decimal("0.01")
ONE_HUNDRED = Decimal("100")

ATWATER_PROTEIN = Decimal("4")
ATWATER_FAT = Decimal("9")
ATWATER_CARB = Decimal("4")


def quantize_dec(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"        # 1.2 — сидячий образ жизни
    LIGHT = "light"                # 1.375 — легкая активность (1-3 тренировки)
    MODERATE = "moderate"          # 1.55 — средняя активность (3-5 тренировок)
    HIGH = "high"                  # 1.725 — высокая активность
    EXTREME = "extreme"            # 1.9 — тяжелый физический труд / спорт


class GoalType(StrEnum):
    DEFICIT = "deficit"            # -15% от TDEE
    MAINTENANCE = "maintenance"    # 100% от TDEE
    SURPLUS = "surplus"            # +15% от TDEE


ACTIVITY_MULTIPLIERS: dict[ActivityLevel, Decimal] = {
    ActivityLevel.SEDENTARY: Decimal("1.2"),
    ActivityLevel.LIGHT: Decimal("1.375"),
    ActivityLevel.MODERATE: Decimal("1.55"),
    ActivityLevel.HIGH: Decimal("1.725"),
    ActivityLevel.EXTREME: Decimal("1.9"),
}

GOAL_MULTIPLIERS: dict[GoalType, Decimal] = {
    GoalType.DEFICIT: Decimal("0.85"),
    GoalType.MAINTENANCE: Decimal("1.00"),
    GoalType.SURPLUS: Decimal("1.15"),
}


@dataclass(frozen=True, slots=True)
class MacroBreakdown:
    declared_calories: Decimal
    atwater_calories: Decimal
    calorie_delta: Decimal
    proteins: Decimal
    fats: Decimal
    carbs: Decimal
    fiber: Decimal


@dataclass(frozen=True, slots=True)
class DailyTargetsResult:
    bmr: Decimal
    tdee: Decimal
    target_calories: Decimal
    target_proteins: Decimal
    target_fats: Decimal
    target_carbs: Decimal
    target_fiber: Decimal
    is_manual: bool


class NutritionDomainService:
    """Чистый доменный сервис расчета макронутриентов и дневных норм."""

    @staticmethod
    def calculate_atwater_calories(
        proteins: Decimal,
        fats: Decimal,
        carbs: Decimal,
    ) -> Decimal:
        raw = (
            proteins * ATWATER_PROTEIN
            + fats * ATWATER_FAT
            + carbs * ATWATER_CARB
        )
        return quantize_dec(raw)

    @classmethod
    def calculate_portion_macros(
        cls,
        *,
        calories_100g: Decimal,
        proteins_100g: Decimal,
        fats_100g: Decimal,
        carbs_100g: Decimal,
        fiber_100g: Decimal,
        grams: Decimal,
    ) -> MacroBreakdown:
        factor = grams / ONE_HUNDRED
        declared_cal = quantize_dec(calories_100g * factor)
        proteins = quantize_dec(proteins_100g * factor)
        fats = quantize_dec(fats_100g * factor)
        carbs = quantize_dec(carbs_100g * factor)
        fiber = quantize_dec(fiber_100g * factor)

        atwater_cal = cls.calculate_atwater_calories(proteins, fats, carbs)
        delta = quantize_dec(declared_cal - atwater_cal)

        return MacroBreakdown(
            declared_calories=declared_cal,
            atwater_calories=atwater_cal,
            calorie_delta=delta,
            proteins=proteins,
            fats=fats,
            carbs=carbs,
            fiber=fiber,
        )

    @classmethod
    def aggregate_macros(cls, items: list[MacroBreakdown]) -> MacroBreakdown:
        total_declared = sum((i.declared_calories for i in items), Decimal("0"))
        total_proteins = sum((i.proteins for i in items), Decimal("0"))
        total_fats = sum((i.fats for i in items), Decimal("0"))
        total_carbs = sum((i.carbs for i in items), Decimal("0"))
        total_fiber = sum((i.fiber for i in items), Decimal("0"))
        total_atwater = sum((i.atwater_calories for i in items), Decimal("0"))

        declared_q = quantize_dec(total_declared)
        atwater_q = quantize_dec(total_atwater)

        return MacroBreakdown(
            declared_calories=declared_q,
            atwater_calories=atwater_q,
            calorie_delta=quantize_dec(declared_q - atwater_q),
            proteins=quantize_dec(total_proteins),
            fats=quantize_dec(total_fats),
            carbs=quantize_dec(total_carbs),
            fiber=quantize_dec(total_fiber),
        )

    @staticmethod
    def calculate_recommended_targets(
        *,
        gender: Gender,
        age: int,
        weight_kg: Decimal,
        height_cm: Decimal,
        activity_level: ActivityLevel,
        goal: GoalType,
    ) -> DailyTargetsResult:
        """
        Расчет по формуле Миффлина — Сан-Жеора:
        BMR = 10 * вес(кг) + 6.25 * рост(см) - 5 * возраст(лет) + s
        где s = +5 для мужчин и -161 для женщин.
        """
        gender_offset = Decimal("5") if gender == Gender.MALE else Decimal("-161")
        bmr_raw = (
            Decimal("10") * weight_kg
            + Decimal("6.25") * height_cm
            - Decimal("5") * Decimal(age)
            + gender_offset
        )
        bmr = max(quantize_dec(bmr_raw), Decimal("800.00"))
        tdee = quantize_dec(bmr * ACTIVITY_MULTIPLIERS[activity_level])
        target_calories = quantize_dec(tdee * GOAL_MULTIPLIERS[goal])

        # Рекомендуемое распределение:
        # Белки: 1.8 г на кг веса тела (оптимум для сохранения/роста мышечной массы)
        # Жиры: 1.0 г на кг веса тела
        # Остаток калорий — углеводы (минимум 50 г)
        # Клетчатка: 14 г на каждые 1000 ккал
        proteins = quantize_dec(weight_kg * Decimal("1.8"))
        fats = quantize_dec(weight_kg * Decimal("1.0"))

        used_calories = proteins * ATWATER_PROTEIN + fats * ATWATER_FAT
        remaining_calories = max(target_calories - used_calories, Decimal("200"))
        carbs = quantize_dec(remaining_calories / ATWATER_CARB)
        fiber = quantize_dec((target_calories / Decimal("1000")) * Decimal("14"))

        return DailyTargetsResult(
            bmr=bmr,
            tdee=tdee,
            target_calories=target_calories,
            target_proteins=proteins,
            target_fats=fats,
            target_carbs=carbs,
            target_fiber=fiber,
            is_manual=False,
        )