"""Telegram bathroom timer bot.

Set BOT_TOKEN in the environment before running:

    BOT_TOKEN=... python main.py
"""

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time as datetime_time, timezone
from zoneinfo import ZoneInfo

from keep_alive import keep_alive
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.environ.get("BOT_TOKEN")

TIMER_OPTIONS = {
    "💩 เข้าห้องน้ำ 25 นาที": ("เข้าห้องน้ำ", 25),
    "💦 ไปฉี่ 10นาที": ("ไปฉี่", 10),
    "🚬 สูบบุหรี่ 7 นาที": ("สูบบุหรี่", 7),
}
RETURN_BUTTON = "🛬 กลับที่นั่ง"
LOCAL_TIMEZONE = ZoneInfo("Asia/Bangkok")
FINE_PER_MINUTE = 50.0
MIDNIGHT_RESET_MESSAGE = (
    "ระบบทำการรีเซ็ตสถิติประจำวันและค่าปรับเรียบร้อยแล้ว! (เวลา 00:00 น.)"
)

REPLY_KEYBOARD = [
    ["💩 เข้าห้องน้ำ 25 นาที"],
    ["💦 ไปฉี่ 10นาที", "🚬 สูบบุหรี่ 7 นาที"],
    ["🛬 กลับที่นั่ง"],
]


@dataclass
class DailyStats:
    """Completed and started bathroom activity for one user and one day."""

    day: date
    total_entries: int = 0
    total_elapsed_seconds: int = 0
    total_fine: float = 0.0
    activities: list[str] = field(default_factory=list)
    active_session: "BathroomSession | None" = None


@dataclass
class BathroomSession:
    """The active timer details needed when a user returns."""

    started_at: datetime
    activity: str
    label: str
    allowed_minutes: int


def keyboard_markup() -> ReplyKeyboardMarkup:
    """Build the persistent keyboard shown at the bottom of the chat."""
    return ReplyKeyboardMarkup(
        REPLY_KEYBOARD,
        resize_keyboard=True,
        is_persistent=True,
    )


def timer_job_name(chat_id: int, user_id: int) -> str:
    """Return the unique job name for a user's timer in a chat."""
    return f"timer:{chat_id}:{user_id}"


def stats_for_user(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int
) -> DailyStats:
    """Get today's stats, resetting this user's record when the date changes."""
    all_stats = context.application.bot_data.setdefault("daily_stats", {})
    key = (chat_id, user_id)
    today = datetime.now(LOCAL_TIMEZONE).date()
    stats = all_stats.get(key)
    if stats is None or stats.day != today:
        stats = DailyStats(day=today)
        all_stats[key] = stats
    return stats


def register_chat(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Remember chats that should receive the daily reset announcement."""
    chat_ids = context.application.bot_data.setdefault("known_chat_ids", set())
    chat_ids.add(chat_id)


def cancel_active_timer(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int
) -> bool:
    """Cancel the user's active timer and report whether one existed."""
    jobs = context.job_queue.get_jobs_by_name(timer_job_name(chat_id, user_id))
    for job in jobs:
        job.schedule_removal()
    return bool(jobs)


async def reset_daily_stats(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset all session stats at midnight in the Bangkok timezone."""
    bot_data = context.application.bot_data
    all_stats = bot_data.setdefault("daily_stats", {})
    chat_ids = set(bot_data.setdefault("known_chat_ids", set()))
    chat_ids.update(chat_id for chat_id, _ in all_stats)

    # Prevent alerts from yesterday's sessions after their stats are removed.
    for chat_id, user_id in list(all_stats):
        cancel_active_timer(context, chat_id, user_id)

    all_stats.clear()
    for chat_id in chat_ids:
        await context.bot.send_message(
            chat_id=chat_id,
            text=MIDNIGHT_RESET_MESSAGE,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the persistent timer keyboard."""
    if update.message is None:
        return

    register_chat(context, update.message.chat_id)
    await update.message.reply_text(
        "🚽 **ระบบบันทึกเวลาเข้าห้องน้ำ**\n"
        "เลือกกิจกรรมจากเมนูด้านล่างเพื่อเริ่มจับเวลา:",
        reply_markup=keyboard_markup(),
        parse_mode="Markdown",
    )


async def keyboard_button_click(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle timer and return actions from the reply keyboard."""
    if update.message is None or update.effective_user is None:
        return

    message = update.message
    user = update.effective_user
    user_mention = f"@{user.username}" if user.username else user.first_name
    user_display_name = user.full_name or user.first_name
    user_summary_name = (
        f"{user_display_name} ({user_mention})"
        if user.username
        else user_display_name
    )
    chat_id = message.chat_id
    register_chat(context, chat_id)
    job_name = timer_job_name(chat_id, user.id)
    stats = stats_for_user(context, chat_id, user.id)

    if message.text == RETURN_BUTTON:
        session = stats.active_session
        if session is None:
            await message.reply_text(
                f"ℹ️ {user_mention} ไม่มีเวลาที่กำลังจับอยู่.",
                reply_markup=keyboard_markup(),
            )
            return

        cancel_active_timer(context, chat_id, user.id)
        elapsed_seconds = max(
            0, int((datetime.now(timezone.utc) - session.started_at).total_seconds())
        )
        elapsed_minutes, seconds = divmod(elapsed_seconds, 60)
        allowed_seconds = session.allowed_minutes * 60
        excess_seconds = max(0, elapsed_seconds - allowed_seconds)
        fine = round(excess_seconds / 60 * FINE_PER_MINUTE, 2)

        stats.total_entries += 1
        stats.total_elapsed_seconds += elapsed_seconds
        stats.total_fine = round(stats.total_fine + fine, 2)
        stats.active_session = None
        total_minutes, total_seconds = divmod(stats.total_elapsed_seconds, 60)
        activity_summary = ", ".join(stats.activities)
        await message.reply_text(
            f"🎉 {user_mention} กลับที่นั่งเรียบร้อยแล้ว!\n"
            f"👤 ผู้ใช้: {user_summary_name}\n"
            f"⏱️ เวลาที่ใช้ไปรอบนี้: {elapsed_minutes} นาที "
            f"{seconds} วินาที\n"
            f"⏳ รวมเวลาที่ใช้ไปทั้งหมดวันนี้: {total_minutes} นาที "
            f"{total_seconds} วินาที\n"
            f"📊 สถิติวันนี้: กดไปแล้วทั้งหมด {stats.total_entries} ครั้ง\n"
            f"    รายการที่กดไปวันนี้: {activity_summary}\n"
            f"💸 ค่าปรับรอบนี้: {fine:g} บาท\n"
            f"💰 รวมค่าปรับสะสมวันนี้: {stats.total_fine:g} บาท",
            reply_markup=keyboard_markup(),
        )
        return

    timer_option = TIMER_OPTIONS.get(message.text or "")
    if timer_option is None:
        return

    activity, minutes = timer_option
    cancel_active_timer(context, chat_id, user.id)
    started_at = datetime.now(timezone.utc)
    stats.active_session = BathroomSession(
        started_at=started_at,
        activity=activity,
        label=message.text or activity,
        allowed_minutes=minutes,
    )
    stats.activities.append(message.text or activity)
    await message.reply_text(
        f"⏱️ {user_mention} เริ่ม{activity}แล้ว!\n"
        f"🕒 จับเวลา {minutes} นาที — ครบกำหนดเวลาแล้วจะแจ้งเตือนในกลุ่ม",
        reply_markup=keyboard_markup(),
    )
    context.job_queue.run_once(
        send_alert,
        minutes * 60,
        chat_id=chat_id,
        data={
            "user": user_mention,
            "activity": activity,
            "minutes": minutes,
            "started_at": started_at,
        },
        name=job_name,
    )


async def send_alert(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an alert when a user's timer reaches its limit."""
    job = context.job
    if job is None or job.chat_id is None:
        return

    await context.bot.send_message(
        chat_id=job.chat_id,
        text=(
            f"🚨 **แจ้งเตือน!** {job.data['user']} "
            f"{job.data['activity']}เกิน {job.data['minutes']} นาทีแล้ว!"
        ),
        parse_mode="Markdown",
    )


def main() -> None:
    """Build and run the Telegram bot."""
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set. Add it to the project's environment secrets."
        )

    keep_alive()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_button_click)
    )
    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue is unavailable. Install python-telegram-bot[job-queue]."
        )
    application.job_queue.run_daily(
        reset_daily_stats,
        time=datetime_time(0, 0, tzinfo=LOCAL_TIMEZONE),
        name="daily-stats-reset",
    )
    application.run_polling()


if __name__ == "__main__":
    main()
