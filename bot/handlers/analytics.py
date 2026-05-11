"""
Analytics dashboard — redesigned.

Today view:  key metrics card + 24h sleep timeline
Week view:   7-day bar chart + daily breakdown table
Month view:  30-day trend + longest sessions
"""
from datetime import datetime, timezone, timedelta, date
from io import BytesIO
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from sqlalchemy import select

from bot.keyboards.inline import analytics_menu_kb
from bot.models import SleepLog, WeightLog, NightReport, SessionLocal
from bot.services.baby import fmt_duration
from bot.services.msg_tracker import replace_section

router = Router()

# Dark palette
BG      = "#0F0F1A"
BG2     = "#1A1A2E"
CARD    = "#16213E"
DAY_C   = "#4FC3F7"
NIGHT_C = "#7C4DFF"
ACC     = "#F06292"
GREEN   = "#66BB6A"
AMBER   = "#FFB74D"
TEXT    = "#E8E8F0"
MUTED   = "#8888AA"
GRID    = "#252540"


async def show_analytics_menu(message: Message):
    sent = await message.answer(
        "📊 *Дашборд*\n\nВыберите период:",
        reply_markup=analytics_menu_kb(),
        parse_mode="Markdown",
    )
    await replace_section(message.bot, message.chat.id, sent.message_id)


@router.callback_query(F.data.startswith("analytics:"))
async def analytics_period(callback: CallbackQuery):
    period = callback.data.split(":")[1]
    await callback.answer("Строю дашборд…")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if period == "today":
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = (now_utc - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = (now_utc - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)

    async with SessionLocal() as s:
        sl_res = await s.execute(
            select(SleepLog)
            .where(SleepLog.started_at >= start)
            .where(SleepLog.ended_at.isnot(None))
            .order_by(SleepLog.started_at.asc())
        )
        sleep_logs = sl_res.scalars().all()

        # Current open sleep (may not be ended)
        open_res = await s.execute(
            select(SleepLog)
            .where(SleepLog.ended_at.is_(None))
            .where(SleepLog.is_night == False)
            .order_by(SleepLog.started_at.desc())
            .limit(1)
        )
        open_sleep = open_res.scalar_one_or_none()

        wt_res = await s.execute(
            select(WeightLog).order_by(WeightLog.measured_at.desc()).limit(2)
        )
        weight_records = wt_res.scalars().all()

    caption = _build_text_summary(sleep_logs, open_sleep, weight_records, period, now_utc)

    if not sleep_logs and not open_sleep:
        await callback.message.answer(
            caption,
            reply_markup=analytics_menu_kb(),
            parse_mode="Markdown",
        )
        return

    buf = _build_chart(sleep_logs, open_sleep, period, now_utc)
    await callback.message.answer_photo(
        BufferedInputFile(buf.read(), filename="dashboard.png"),
        caption=caption,
        reply_markup=analytics_menu_kb(),
        parse_mode="Markdown",
    )


# ── Text summary ──────────────────────────────────────────────────────────────

def _build_text_summary(sleep_logs, open_sleep, weight_records, period, now_utc) -> str:
    from bot.config import BABY_NAME

    completed = [s for s in sleep_logs if s.ended_at]
    total_sec = sum(int((s.ended_at - s.started_at).total_seconds()) for s in completed)
    n_sessions = len(completed)

    # Current status
    if open_sleep:
        elapsed = int((now_utc - open_sleep.started_at).total_seconds())
        status_line = f"😴 Сейчас спит — {fmt_duration(elapsed)}"
    elif completed:
        last = completed[-1]
        awake = int((now_utc - last.ended_at).total_seconds())
        status_line = f"🌞 Не спит — {fmt_duration(awake)}"
    else:
        status_line = "📭 Нет данных о сне"

    # Longest session
    longest = max((int((s.ended_at - s.started_at).total_seconds()) for s in completed), default=0)

    # Day/night split
    day_sec   = sum(int((s.ended_at - s.started_at).total_seconds()) for s in completed if not s.is_night)
    night_sec = sum(int((s.ended_at - s.started_at).total_seconds()) for s in completed if s.is_night)

    period_labels = {"today": "сегодня", "week": "за 7 дней", "month": "за 30 дней"}
    label = period_labels.get(period, period)

    lines = [f"📊 *Дашборд — {label}*\n", status_line, ""]

    if total_sec or open_sleep:
        lines.append(f"⏱ Всего сна: *{fmt_duration(total_sec)}*")
        if n_sessions:
            avg = total_sec // n_sessions
            lines.append(f"📐 Сессий: *{n_sessions}*, ср. *{fmt_duration(avg)}*")
        if longest:
            lines.append(f"🏆 Самая долгая: *{fmt_duration(longest)}*")
        if day_sec and night_sec:
            lines.append(f"☀️ Дневной: *{fmt_duration(day_sec)}*  🌙 Ночной: *{fmt_duration(night_sec)}*")

    # Norm check (newborn: 14-17h/day)
    if period == "today" and total_sec > 0:
        target = 14 * 3600
        pct = total_sec / target * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        lines.append(f"\n📈 От нормы 14ч: `{bar}` {pct:.0f}%")

    if period == "week" and n_sessions >= 2:
        avg_per_day = total_sec / 7
        lines.append(f"\n📅 Среднее/день: *{fmt_duration(int(avg_per_day))}*")

    # Weight
    if weight_records:
        last_w = weight_records[0]
        kg = last_w.grams / 1000
        lines.append(f"\n⚖️ Последний вес: *{kg:.3f} кг*")
        if len(weight_records) == 2:
            delta = last_w.grams - weight_records[1].grams
            sign = "+" if delta >= 0 else ""
            lines.append(f"   Динамика: {sign}{delta} г")

    return "\n".join(lines)


# ── Chart ─────────────────────────────────────────────────────────────────────

def _build_chart(sleep_logs, open_sleep, period, now_utc) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.dates as mdates
    import matplotlib.ticker as ticker
    import pytz
    import numpy as np
    from bot.config import TZ

    tz = pytz.timezone(TZ)

    if period == "today":
        return _chart_today(sleep_logs, open_sleep, now_utc, tz)
    else:
        days = 7 if period == "week" else 30
        return _chart_days(sleep_logs, days, tz, now_utc)


def _chart_today(sleep_logs, open_sleep, now_utc, tz) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch
    import pytz

    fig = plt.figure(figsize=(10, 5), facecolor=BG)
    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[1, 2], hspace=0.35)

    # ── Row 1: Metric cards ────────────────────────────────────────────────────
    ax_cards = fig.add_subplot(gs[0])
    ax_cards.set_facecolor(BG)
    ax_cards.axis("off")

    completed = [s for s in sleep_logs if s.ended_at]
    total_sec = sum(int((s.ended_at - s.started_at).total_seconds()) for s in completed)
    n = len(completed)
    longest = max((int((s.ended_at - s.started_at).total_seconds()) for s in completed), default=0)

    if open_sleep:
        elapsed = int((now_utc - open_sleep.started_at).total_seconds())
        current_lbl = f"😴 {fmt_duration(elapsed)}"
    else:
        current_lbl = "🌞 Не спит"

    metrics = [
        ("Статус", current_lbl),
        ("Всего сна", fmt_duration(total_sec)),
        ("Сессий", str(n)),
        ("Лучший сон", fmt_duration(longest)),
    ]

    n_cards = len(metrics)
    card_w = 0.22
    gap = (1 - n_cards * card_w) / (n_cards + 1)

    for i, (title, value) in enumerate(metrics):
        x = gap + i * (card_w + gap)
        rect = FancyBboxPatch((x, 0.05), card_w, 0.85,
                               boxstyle="round,pad=0.02",
                               facecolor=CARD, edgecolor=GRID, linewidth=1,
                               transform=ax_cards.transAxes, clip_on=False)
        ax_cards.add_patch(rect)
        ax_cards.text(x + card_w / 2, 0.70, title, ha="center", va="center",
                      color=MUTED, fontsize=8, transform=ax_cards.transAxes)
        ax_cards.text(x + card_w / 2, 0.30, value, ha="center", va="center",
                      color=TEXT, fontsize=12, fontweight="bold", transform=ax_cards.transAxes)

    # ── Row 2: 24h timeline ────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[1])
    ax.set_facecolor(BG2)

    ax.set_xlim(0, 24)
    ax.set_ylim(0, 1)

    for h in range(0, 25, 2):
        ax.axvline(h, color=GRID, linewidth=0.8, zorder=1)

    # Fill awake background
    ax.axhspan(0, 1, facecolor=BG2, zorder=0)

    # Draw sleep blocks
    all_logs = list(sleep_logs)
    if open_sleep:
        # Add open sleep up to now
        fake = type('S', (), {
            'started_at': open_sleep.started_at,
            'ended_at': now_utc,
            'is_night': False
        })()
        all_logs.append(fake)

    for s in all_logs:
        start_local = pytz.utc.localize(s.started_at).astimezone(tz)
        end_local   = pytz.utc.localize(s.ended_at).astimezone(tz)
        x0 = start_local.hour + start_local.minute / 60
        x1 = end_local.hour   + end_local.minute / 60
        if x1 < x0:
            x1 = 24
        color = NIGHT_C if s.is_night else DAY_C
        width = max(x1 - x0, 0.1)
        rect = mpatches.FancyBboxPatch(
            (x0, 0.1), width, 0.8,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor="none", alpha=0.88, zorder=2
        )
        ax.add_patch(rect)
        if width > 0.6:
            dur = fmt_duration(int((s.ended_at - s.started_at).total_seconds()))
            ax.text(x0 + width / 2, 0.5, dur,
                    ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold", zorder=3)

    # Current time marker
    now_local = pytz.utc.localize(now_utc).astimezone(tz)
    now_h = now_local.hour + now_local.minute / 60
    ax.axvline(now_h, color=ACC, linewidth=1.5, linestyle="--", zorder=4)
    ax.text(now_h, 0.95, "сейчас", color=ACC, fontsize=7, ha="center", va="top", zorder=5)

    # Norm target bar (14h shaded)
    ax.axvspan(0, 14, alpha=0.04, color=GREEN, zorder=0)

    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)],
                       color=MUTED, fontsize=7.5, rotation=30, ha="right")
    ax.yaxis.set_visible(False)
    ax.set_title("Сон за сегодня (24ч)", color=TEXT, fontsize=10, pad=8)

    for sp in ax.spines.values():
        sp.set_color(GRID)

    day_p   = mpatches.Patch(color=DAY_C,   label="Дневной")
    night_p = mpatches.Patch(color=NIGHT_C, label="Ночной")
    ax.legend(handles=[day_p, night_p], loc="upper right",
              facecolor=CARD, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    fig.tight_layout(pad=1.2)
    return _to_buf(fig)


def _chart_days(sleep_logs, num_days: int, tz, now_utc) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import matplotlib.gridspec as gridspec
    import numpy as np
    import pytz

    today = pytz.utc.localize(now_utc).astimezone(tz).date()
    days = [(today - timedelta(days=i)) for i in range(num_days - 1, -1, -1)]

    day_sleep  = {d: 0 for d in days}
    night_sleep = {d: 0 for d in days}

    for s in sleep_logs:
        local_d = pytz.utc.localize(s.started_at).astimezone(tz).date()
        dur = int((s.ended_at - s.started_at).total_seconds())
        if local_d in day_sleep:
            if s.is_night:
                night_sleep[local_d] += dur
            else:
                day_sleep[local_d] += dur

    vals_day   = [day_sleep[d] / 3600 for d in days]
    vals_night = [night_sleep[d] / 3600 for d in days]
    totals     = [d + n for d, n in zip(vals_day, vals_night)]

    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG)
    ax.set_facecolor(BG2)

    x = np.arange(len(days))
    bar_w = 0.65

    ax.bar(x, vals_day,   bar_w, color=DAY_C,   label="Дневной", alpha=0.88, zorder=2)
    ax.bar(x, vals_night, bar_w, color=NIGHT_C, label="Ночной",
           bottom=vals_day, alpha=0.88, zorder=2)

    # Norm reference line
    ax.axhline(14, color=AMBER, linewidth=1.2, linestyle="--", alpha=0.8, zorder=3)
    ax.axhline(17, color=GREEN, linewidth=0.8, linestyle=":",  alpha=0.6, zorder=3)
    ax.text(len(x) - 0.5, 14.1, "min норма 14ч", color=AMBER, fontsize=7.5,
            va="bottom", ha="right", zorder=4)

    # Average line
    valid = [t for t in totals if t > 0]
    if valid:
        avg = sum(valid) / len(valid)
        ax.axhline(avg, color=ACC, linewidth=1.5, linestyle="-", alpha=0.7, zorder=3)
        ax.text(0.01, avg + 0.1, f"ср {avg:.1f}ч", color=ACC, fontsize=7.5,
                transform=ax.get_yaxis_transform(), va="bottom", zorder=4)

    # Value labels
    for i, t in enumerate(totals):
        if t > 0.3:
            ax.text(i, t + 0.1, f"{t:.1f}ч", ha="center", va="bottom",
                    fontsize=7.5, color=TEXT, fontweight="bold", zorder=5)

    step = max(1, len(days) // 8)
    labels = [d.strftime("%d.%m") for d in days]
    ax.set_xticks(x)
    ax.set_xticklabels(
        [labels[i] if i % step == 0 else "" for i in range(len(labels))],
        color=MUTED, fontsize=8, rotation=30, ha="right"
    )
    ax.yaxis.set_major_locator(ticker.MultipleLocator(2))
    ax.tick_params(axis="y", colors=MUTED, labelsize=8)
    ax.set_ylabel("часов", color=MUTED, fontsize=9)
    ax.set_title(
        f"Сон за {'7 дней' if num_days == 7 else '30 дней'}",
        color=TEXT, fontsize=11, pad=10
    )
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    for sp in ax.spines.values():
        sp.set_color(GRID)

    ax.legend(facecolor=CARD, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
    fig.tight_layout(pad=1.2)
    return _to_buf(fig)


def _to_buf(fig) -> BytesIO:
    import matplotlib.pyplot as plt
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
