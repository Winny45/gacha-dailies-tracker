"""Static per-game config: display name, reset schedule, and recurring tasks.

Reset schedules and task lists are hand-maintained here (they change rarely).
Events/banners, which change constantly, are NOT here -- see scrapers/.

Time estimates are ballpark figures for an average-progress account (not a
brand new or a maxed-out whale account) -- good enough for a "how long is
today going to take me" total, not a speedrun record.
"""
from __future__ import annotations

from dataclasses import dataclass

from data.schema import Period, ResetSchedule, Task


@dataclass(frozen=True)
class GameConfig:
    id: str
    name: str
    reset: ResetSchedule
    tasks: tuple[Task, ...]


def _t(
    game_id: str,
    task_id: str,
    label: str,
    period: Period,
    minutes: int,
    note: str = "",
) -> Task:
    return Task(
        id=f"{game_id}.{task_id}",
        game_id=game_id,
        label=label,
        period=period,
        estimated_minutes=minutes,
        note=note,
    )


GAMES: dict[str, GameConfig] = {}


def register(game: GameConfig) -> None:
    GAMES[game.id] = game


# ---------------------------------------------------------------------------
# Brown Dust 2
# Reset: daily 00:00 UTC, not DST-adjusted. Weekly systems (Mirror Wars,
# Guild Raid) align to the same Monday 00:00 UTC boundary.
# Source: browndust2.miraheze.org/wiki/Daily_reset
# ---------------------------------------------------------------------------
register(
    GameConfig(
        id="brown_dust_2",
        name="Brown Dust 2",
        reset=ResetSchedule(
            daily_reset_hour_utc=0,
            weekly_reset_weekday=0,  # Monday 00:00 UTC
            weekly_reset_hour_utc=0,
            tz_note="00:00 UTC daily, not DST-adjusted",
        ),
        tasks=(
            _t("brown_dust_2", "featured_draws", "Collect free daily draws on featured banners", Period.DAILY, 1),
            _t("brown_dust_2", "mailbox", "Collect login/mailbox items", Period.DAILY, 1),
            _t("brown_dust_2", "rice", "Spend 60 cooked rice (Hunting Grounds)", Period.DAILY, 10),
            _t("brown_dust_2", "torches", "Spend 60 torches (Elemental Caves)", Period.DAILY, 10),
            _t("brown_dust_2", "pass_dailies", "Craft/dismantle/upgrade/refine gear (pass dailies)", Period.DAILY, 5),
            _t("brown_dust_2", "field_finds", "Collect field finds and Gluttis", Period.DAILY, 3),
            _t("brown_dust_2", "mirror_wars_daily", "Battle in Mirror Wars (PvP)", Period.DAILY, 5),
            _t("brown_dust_2", "territory", "Collect Territory dispatch + Last Night rewards", Period.DAILY, 2),
            _t("brown_dust_2", "mirror_wars_weekly", "Mirror Wars season ranking push (Mon-Sun)", Period.WEEKLY, 15),
            _t("brown_dust_2", "guild_raid", "Guild Raid (Day1-3 prep, Day4-7 Boss Defense)", Period.WEEKLY, 10),
            _t("brown_dust_2", "pass_weekly", "Weekly/seasonal pass quests", Period.WEEKLY, 5),
        ),
    )
)

# ---------------------------------------------------------------------------
# NIKKE (Global -- single worldwide server)
# Reset: daily 20:00 UTC (= 05:00 UTC+9, the game's reference timezone);
# weekly reset Monday at the same time. Community consensus is not 100%
# unanimous on the exact hour -- verify in-game if countdowns look off.
# Source: @NIKKE_en patch notes (UTC+9 reference), GachaList/Game-Time-Master.
# ---------------------------------------------------------------------------
register(
    GameConfig(
        id="nikke",
        name="NIKKE",
        reset=ResetSchedule(
            daily_reset_hour_utc=20,
            weekly_reset_weekday=0,  # Monday UTC (~05:00 Monday UTC+9)
            weekly_reset_hour_utc=20,
            tz_note="game's reference timezone is UTC+9; daily reset ~05:00 UTC+9",
        ),
        tasks=(
            _t("nikke", "sim_room", "Simulation Room (sectors A/B/C, 5 levels)", Period.DAILY, 8),
            _t("nikke", "outpost", "Outpost Defense 'Wipe Out' (1 free + paid refills)", Period.DAILY, 3),
            _t("nikke", "tribe_tower", "Tribe Tower challenges (today's rotating manufacturer)", Period.DAILY, 5),
            _t("nikke", "daily_quests", "Day-by-day daily quests", Period.DAILY, 2),
            _t("nikke", "advice", "Advice sessions (daily free counseling)", Period.DAILY, 3),
            _t("nikke", "interception", "Interception attempts (if boss window active)", Period.DAILY, 5),
            _t("nikke", "weekly_quests", "Weekly mission set", Period.WEEKLY, 3),
            _t("nikke", "coop", "Co-op raid weekly attempts", Period.WEEKLY, 10),
            _t("nikke", "special_archive", "Special Archive / story limited attempts", Period.WEEKLY, 15),
            _t("nikke", "weekly_mail", "Claim weekly gifts/mail", Period.WEEKLY, 2),
        ),
    )
)

# ---------------------------------------------------------------------------
# Blue Archive
# Reset: daily 04:00 JST -> 19:00 UTC (previous day); weekly Tuesday 04:00 JST
# -> Monday 19:00 UTC. Banner rotation dates are read live per-row by the
# scraper, NOT derived from this schedule (they don't follow the daily clock).
# Source: bluearchive.wiki "Tasks" page + bluearchive.gg
# ---------------------------------------------------------------------------
register(
    GameConfig(
        id="blue_archive",
        name="Blue Archive",
        reset=ResetSchedule(
            daily_reset_hour_utc=19,
            weekly_reset_weekday=0,  # Monday (reset lands at start of Tuesday JST)
            weekly_reset_hour_utc=19,
            tz_note="04:00 JST daily / 04:00 JST Tuesday (weekly)",
        ),
        tasks=(
            _t("blue_archive", "cafe", "Open Cafe / collect Bond points", Period.DAILY, 2),
            _t("blue_archive", "lesson", "Hold a Lesson x2", Period.DAILY, 2),
            _t("blue_archive", "ap_recharge", "Use an AP recharge", Period.DAILY, 1),
            _t("blue_archive", "bounty", "Clear Bounty x3", Period.DAILY, 5),
            _t("blue_archive", "commission", "Clear Commissions", Period.DAILY, 2),
            _t("blue_archive", "scrimmage", "Clear Scrimmage (PvP) x1", Period.DAILY, 5),
            _t("blue_archive", "craft", "Craft an item", Period.DAILY, 2),
            _t("blue_archive", "missions", "Clear daily Missions/Hard stages", Period.DAILY, 10),
            _t("blue_archive", "lesson_w", "Hold Lesson x9 (weekly total)", Period.WEEKLY, 5),
            _t("blue_archive", "bounty_w", "Clear Bounty (weekly total)", Period.WEEKLY, 10),
            _t("blue_archive", "scrimmage_w", "Clear Scrimmage (weekly total)", Period.WEEKLY, 10),
            _t("blue_archive", "hard_w", "Clear Hard stages (weekly total)", Period.WEEKLY, 15),
            _t(
                "blue_archive",
                "total_assault",
                "Total Assault raid (when active: 3 tickets/day, ~biweekly 7-day window)",
                Period.WEEKLY,
                10,
                note="Not always active -- check Events tab for current window.",
            ),
        ),
    )
)

# ---------------------------------------------------------------------------
# Limbus Company
# Reset: daily 06:00 KST -> 21:00 UTC (previous day); weekly reset Friday
# 06:00 KST -> Thursday 21:00 UTC. Source: community-confirmed, cross-check
# periodically against https://limbuscompany.wiki.gg/wiki/Mirror_Dungeon
# ---------------------------------------------------------------------------
register(
    GameConfig(
        id="limbus",
        name="Limbus Company",
        reset=ResetSchedule(
            daily_reset_hour_utc=21,
            weekly_reset_weekday=3,  # Thursday (reset lands at start of Friday KST)
            weekly_reset_hour_utc=21,
            tz_note="06:00 KST daily / 06:00 KST Friday (weekly)",
        ),
        tasks=(
            _t("limbus", "enkephalin", "Assemble 1 Enkephalin Module", Period.DAILY, 1),
            _t("limbus", "exp_lux", "Clear EXP Luxcavation x1", Period.DAILY, 5),
            _t("limbus", "thread_lux", "Clear Thread Luxcavation x1 (first 3/day = double Thread)", Period.DAILY, 5),
            _t("limbus", "any_stage_2", "Clear any stage x2", Period.DAILY, 6),
            _t("limbus", "defeat_10", "Defeat 10 enemies", Period.DAILY, 3),
            _t("limbus", "exp_lux_w", "Clear EXP Luxcavation x5", Period.WEEKLY, 20),
            _t("limbus", "thread_lux_w", "Clear Thread Luxcavation x5", Period.WEEKLY, 20),
            _t("limbus", "any_stage_10", "Clear any stage x10", Period.WEEKLY, 25),
            _t("limbus", "defeat_100", "Defeat 100 enemies", Period.WEEKLY, 5),
            _t("limbus", "mirror_dungeon", "Enter Mirror Dungeon x1 (3 weekly bonus charges)", Period.WEEKLY, 30),
        ),
    )
)
