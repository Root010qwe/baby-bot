"""Weight tracker: input in grams + matplotlib chart."""
from datetime import datetime
from io import BytesIO
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.keyboards.inline import weight_menu_kb
from bot.models import WeightLog, SessionLocal
from bot.services.msg_tracker import replace_section

router = Router()


class WeightStates(StatesGroup):
    waiting_grams = State()


async def show_weight_menu(message: Message):
    async with SessionLocal() as s:
        res = await s.execute(
            select(WeightLog).order_by(WeightLog.measured_at.desc()).limit(1)
        )
        last = res.scalar_one_or_none()

    last_text = ""
    if last:
        kg = last.grams / 1000
        last_text = f"\n_Последний: {kg:.3f} кг_"

    sent = await message.answer(
        f"⚖️ *Вес*{last_text}",
        reply_markup=weight_menu_kb(),
        parse_mode="Markdown",
    )
    await replace_section(message.bot, message.chat.id, sent.message_id)


@router.callback_query(F.data == "weight:add")
async def weight_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(WeightStates.waiting_grams)
    await callback.message.answer(
        "Введи вес в граммах (например: *4250*) или в кг (например: *4.25*):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(WeightStates.waiting_grams)
async def weight_input(message: Message, state: FSMContext):
    text = message.text.strip().replace(",", ".")
    try:
        if "." in text:
            grams = int(float(text) * 1000)
        else:
            grams = int(text)
        if grams < 500 or grams > 20000:
            raise ValueError
    except (ValueError, OverflowError):
        await message.answer("Введи корректно: в граммах (4250) или кг (4.25)")
        return

    await state.clear()
    async with SessionLocal() as s:
        log = WeightLog(grams=grams, measured_at=datetime.utcnow())
        s.add(log)
        await s.commit()

    kg = grams / 1000
    await message.answer(
        f"✅ Вес записан: *{kg:.3f} кг* ({grams} г)",
        reply_markup=weight_menu_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "weight:chart")
async def weight_chart(callback: CallbackQuery):
    await callback.answer("Строю график…")
    async with SessionLocal() as s:
        res = await s.execute(
            select(WeightLog).order_by(WeightLog.measured_at.asc())
        )
        records = res.scalars().all()

    if len(records) < 2:
        await callback.message.answer(
            "Нужно минимум 2 записи для графика.",
            reply_markup=weight_menu_kb(),
        )
        return

    buf = _build_weight_chart(records)
    await callback.message.answer_photo(
        BufferedInputFile(buf.read(), filename="weight.png"),
        caption="📈 График веса",
        reply_markup=weight_menu_kb(),
    )


def _build_weight_chart(records) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import pytz
    from bot.config import TZ

    C_BG   = "#1E1E2E"
    C_GRID = "#2E2E4E"
    C_TEXT = "#E0E0E0"
    C_LINE = "#66BB6A"
    C_DOT  = "#A5D6A7"
    C_FILL = "#2E4A2E"

    tz = pytz.timezone(TZ)
    dates = [pytz.utc.localize(r.measured_at).astimezone(tz) for r in records]
    weights_kg = [r.grams / 1000 for r in records]

    fig, ax = plt.subplots(figsize=(9, 4), facecolor=C_BG)
    ax.set_facecolor(C_BG)

    # Fill under the line
    ax.fill_between(dates, weights_kg, min(weights_kg) - 0.05,
                    color=C_FILL, alpha=0.5, zorder=1)

    ax.plot(dates, weights_kg, "-", color=C_LINE, linewidth=2.5, zorder=2)
    ax.scatter(dates, weights_kg, color=C_DOT, s=60, zorder=3)

    for d, w in zip(dates, weights_kg):
        ax.annotate(
            f"{w:.3f}", (d, w),
            textcoords="offset points", xytext=(0, 10),
            ha="center", fontsize=8.5, color=C_TEXT, fontweight="bold",
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)

    ax.tick_params(colors=C_TEXT, labelsize=8)
    ax.set_ylabel("кг", color=C_TEXT, fontsize=9)
    ax.set_title("📈 Динамика веса", color=C_TEXT, fontsize=11, pad=10)
    ax.grid(True, color=C_GRID, linewidth=0.6)
    for spine in ax.spines.values():
        spine.set_color(C_GRID)

    # Delta annotation
    delta = weights_kg[-1] - weights_kg[0]
    sign = "+" if delta >= 0 else ""
    ax.text(0.02, 0.05, f"Прирост: {sign}{delta*1000:.0f} г",
            transform=ax.transAxes, color=C_DOT, fontsize=9,
            va="bottom", ha="left")

    fig.tight_layout(pad=1.2)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=C_BG)
    plt.close(fig)
    buf.seek(0)
    return buf
