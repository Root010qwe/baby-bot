"""Analytics: beautiful sleep charts for today / week / month."""
from datetime import datetime, timezone, timedelta, date
from io import BytesIO
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from sqlalchemy import select

from bot.keyboards.inline import analytics_menu_kb
from bot.models import SleepLog, SessionLocal
from bot.services.baby import fmt_duration
from bot.services.msg_tracker import replace_section

router = Router()

# Palette
C_DAY   = "#64B5F6"   # light blue — day sleep
C_NIGHT = "#5C6BC0"   # indigo — night sleep
C_BG    = "#1E1E2E"   # dark background
C_GRID  = "#2E2E4E"
C_TEXT  = "#E0E0E0"
C_AXIS  = "#9E9EBF"


async def show_analytics_menu(message: Message):
    sent = await message.answer(
        "📊 *Статистика*\n\nВыберите период:",
        reply_markup=analytics_menu_kb(),
        parse_mode="Markdown",
    )
    await replace_section(message.bot, message.chat.id, sent.message_id)


@router.callback_query(F.data.startswith("analytics:"))
async def analytics_period(callback: CallbackQuery):
    period = callback.data.split(":")[1]
    await callback.answer("Строю…")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "today":
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "сегодня"
    elif period == "week":
        start = now_utc - timedelta(days=6)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "7 дней"
    else:
        start = now_utc - timedelta(days=29)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "30 дней"

    async with SessionLocal() as s:
        res = await s.execute(
            select(SleepLog)
            .where(SleepLog.started_at >= start)
            .where(SleepLog.ended_at.isnot(None))
            .order_by(SleepLog.started_at.asc())
        )
        sleep_logs = res.scalars().all()

    if not sleep_logs:
        await callback.message.answer(
            f"📊 *{label.capitalize()}*\n\nДанных пока нет.",
            reply_markup=analytics_menu_kb(),
            parse_mode="Markdown",
        )
        return

    if period == "today":
        buf = _chart_today(sleep_logs)
    else:
        days = 7 if period == "week" else 30
        buf = _chart_days(sleep_logs, days, label)

    summary = _build_summary(sleep_logs)
    await callback.message.answer_photo(
        BufferedInputFile(buf.read(), filename="stats.png"),
        caption=summary,
        reply_markup=analytics_menu_kb(),
        parse_mode="Markdown",
    )


def _build_summary(logs) -> str:
    total = sum(int((s.ended_at - s.started_at).total_seconds()) for s in logs)
    n = len(logs)
    avg = total // n if n else 0
    return (
        f"📊 *Статистика сна*\n"
        f"Всего: *{fmt_duration(total)}* за {n} сесс.\n"
        f"Средняя сессия: *{fmt_duration(avg)}*"
    )


# ── Chart: today — 24h horizontal timeline ────────────────────────────────────

def _chart_today(logs) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import pytz
    from bot.config import TZ

    tz = pytz.timezone(TZ)

    fig, ax = plt.subplots(figsize=(10, 3), facecolor=C_BG)
    ax.set_facecolor(C_BG)

    # 24h axis in hours (0–24)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 1)

    # Hour grid
    for h in range(0, 25, 3):
        ax.axvline(h, color=C_GRID, linewidth=0.8, zorder=1)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 3)],
                       color=C_TEXT, fontsize=9)
    ax.yaxis.set_visible(False)

    for spine in ax.spines.values():
        spine.set_color(C_GRID)

    # Draw sleep blocks
    for s in logs:
        start_local = pytz.utc.localize(s.started_at).astimezone(tz)
        end_local   = pytz.utc.localize(s.ended_at).astimezone(tz)
        x0 = start_local.hour + start_local.minute / 60
        x1 = end_local.hour + end_local.minute / 60
        if x1 <= x0:
            x1 = 24  # clamp overnight
        color = C_NIGHT if s.is_night else C_DAY
        width = x1 - x0
        rect = mpatches.FancyBboxPatch(
            (x0, 0.15), width, 0.7,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor="none", alpha=0.92, zorder=2
        )
        ax.add_patch(rect)
        # Duration label inside block if wide enough
        if width > 0.5:
            dur = fmt_duration(int((s.ended_at - s.started_at).total_seconds()))
            ax.text(x0 + width / 2, 0.5, dur,
                    ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold", zorder=3)

    today_str = date.today().strftime("%d.%m.%Y")
    ax.set_title(f"Сон сегодня ({today_str})", color=C_TEXT, fontsize=11, pad=10)

    day_p = mpatches.Patch(color=C_DAY, label="Дневной")
    night_p = mpatches.Patch(color=C_NIGHT, label="Ночной")
    ax.legend(handles=[day_p, night_p], loc="upper right",
              facecolor=C_BG, edgecolor=C_GRID, labelcolor=C_TEXT, fontsize=8)

    fig.tight_layout(pad=1.2)
    return _to_buf(fig)


# ── Chart: week/month — bars per day ─────────────────────────────────────────

def _chart_days(logs, num_days: int, label: str) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import pytz
    import numpy as np
    from bot.config import TZ

    tz = pytz.timezone(TZ)

    # Build per-day totals
    today = date.today()
    days = [(today - timedelta(days=i)) for i in range(num_days - 1, -1, -1)]
    day_sleep = {d: 0 for d in days}   # seconds day
    day_night = {d: 0 for d in days}   # seconds night

    for s in logs:
        local = pytz.utc.localize(s.started_at).astimezone(tz).date()
        dur = int((s.ended_at - s.started_at).total_seconds())
        if local in day_sleep:
            if s.is_night:
                day_night[local] += dur
            else:
                day_sleep[local] += dur

    x = list(range(len(days)))
    vals_day   = [day_sleep[d] / 3600 for d in days]
    vals_night = [day_night[d] / 3600 for d in days]

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=C_BG)
    ax.set_facecolor(C_BG)

    bar_w = 0.65
    bars_day   = ax.bar(x, vals_day,   bar_w, color=C_DAY,   label="Дневной", zorder=2)
    bars_night = ax.bar(x, vals_night, bar_w, color=C_NIGHT,
                        bottom=vals_day, label="Ночной", zorder=2)

    # Newborn norm reference line ~14–16h
    ax.axhline(14, color="#FFB74D", linewidth=1, linestyle="--", alpha=0.7, zorder=3)
    ax.text(len(x) - 0.5, 14.15, "норма 14ч",
            color="#FFB74D", fontsize=7.5, va="bottom", ha="right", zorder=4)

    # Labels on bars: total if > 0
    for i, (d, n) in enumerate(zip(vals_day, vals_night)):
        total = d + n
        if total > 0.1:
            ax.text(i, total + 0.15, f"{total:.1f}ч",
                    ha="center", va="bottom", fontsize=7.5,
                    color=C_TEXT, fontweight="bold", zorder=5)

    labels = [d.strftime("%d.%m") for d in days]
    # Show every N-th label to avoid crowding
    step = max(1, len(days) // 10)
    ax.set_xticks(x)
    ax.set_xticklabels(
        [labels[i] if i % step == 0 else "" for i in range(len(labels))],
        color=C_TEXT, fontsize=8, rotation=30, ha="right"
    )

    ax.yaxis.set_major_locator(ticker.MultipleLocator(2))
    ax.tick_params(axis="y", colors=C_AXIS, labelsize=8)
    ax.set_ylabel("Часов", color=C_AXIS, fontsize=9)
    ax.set_title(f"Сон за {label}", color=C_TEXT, fontsize=11, pad=10)
    ax.grid(axis="y", color=C_GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_color(C_GRID)

    ax.legend(facecolor=C_BG, edgecolor=C_GRID, labelcolor=C_TEXT, fontsize=8)

    fig.tight_layout(pad=1.2)
    return _to_buf(fig)


def _to_buf(fig) -> BytesIO:
    import matplotlib.pyplot as plt
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
