from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("calories_100g >= 0 AND calories_100g <= 900", name="chk_cal_range"),
        CheckConstraint(
            "proteins_100g >= 0 AND fats_100g >= 0 AND carbs_100g >= 0 AND fiber_100g >= 0",
            name="chk_macros_non_negative",
        ),
        CheckConstraint(
            "proteins_100g + fats_100g + carbs_100g + fiber_100g <= 100.00",
            name="chk_dry_matter_limit",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    calories_100g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    proteins_100g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fats_100g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    carbs_100g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fiber_100g: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    units: Mapped[list["ProductUnit"]] = relationship(
        "ProductUnit",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProductUnit(Base):
    __tablename__ = "product_units"
    __table_args__ = (
        CheckConstraint("grams_per_unit > 0 AND grams_per_unit <= 10000", name="chk_unit_grams_positive"),
        UniqueConstraint("product_id", "unit_name", name="uq_product_unit_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_name: Mapped[str] = mapped_column(String(80), nullable=False)
    grams_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="units")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="male")
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("75.00"))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("180.00"))
    activity_level: Mapped[str] = mapped_column(String(32), nullable=False, default="moderate")
    goal: Mapped[str] = mapped_column(String(32), nullable=False, default="maintenance")

    use_manual_targets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manual_calories: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("2500.00"))
    manual_proteins: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("140.00"))
    manual_fats: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("80.00"))
    manual_carbs: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("300.00"))
    manual_fiber: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("30.00"))


class DailyLogEntry(Base):
    __tablename__ = "daily_log_entries"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND quantity <= 10000", name="chk_quantity_positive"),
        CheckConstraint("total_grams > 0 AND total_grams <= 20000", name="chk_total_grams_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    unit_label: Mapped[str] = mapped_column(String(80), nullable=False, default="г")
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_grams: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product: Mapped["Product"] = relationship("Product", lazy="joined")


class DailyMacroFact(Base):
    """Прямой ввод фактических БЖУК (и опционально ккал) за день без подсчета продуктов."""

    __tablename__ = "daily_macro_facts"
    __table_args__ = (
        UniqueConstraint("log_date", name="uq_daily_macro_fact_date"),
        CheckConstraint(
            "declared_calories >= 0 AND declared_calories <= 30000",
            name="chk_fact_cal_range",
        ),
        CheckConstraint(
            "proteins >= 0 AND proteins <= 3000 AND "
            "fats >= 0 AND fats <= 3000 AND "
            "carbs >= 0 AND carbs <= 5000 AND "
            "fiber >= 0 AND fiber <= 1000",
            name="chk_fact_macros_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    declared_calories: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    proteins: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fats: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    carbs: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fiber: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    combine_with_products: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )