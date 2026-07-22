from __future__ import annotations

import asyncio
import time

from . import live_timeline_v2 as timeline
from . import live_ts_proxy as legacy
from . import main

CATCH_UP_BUDGET_SECONDS = 1.25
MAX_CATCH_UP_PACKETS = 40_000


async def _catch_up_replacement_v3(
    replacement: timeline.PreparedReplacementV2,
    normalizer: timeline.MultiClockTimelineNormalizer,
    session_id: str,
) -> timeline.PreparedReplacementV2:
    target = normalizer.last_source_video_pts
    anchor = replacement.source_anchor
    if target is None or anchor is None or timeline._pts_at_or_after(anchor, target):
        return replacement

    candidate: list[bytes] = []
    candidate_anchor: int | None = None
    newest_complete: list[bytes] | None = None
    newest_anchor: int | None = None
    deadline = time.monotonic() + CATCH_UP_BUDGET_SECONDS
    read_packets = 0

    try:
        while time.monotonic() < deadline and read_packets < MAX_CATCH_UP_PACKETS:
            chunk = await asyncio.wait_for(
                replacement.connection.iterator.__anext__(),
                timeout=0.75,
            )
            for packet in legacy._split_packets(
                legacy._aligned_ts_payload(replacement.connection, chunk)
            ):
                read_packets += 1
                if legacy._contains_random_access(packet, normalizer.video_pids):
                    if (
                        candidate_anchor is not None
                        and len(candidate) >= timeline.MIN_SWITCH_CONTEXT_PACKETS
                    ):
                        newest_complete = candidate
                        newest_anchor = candidate_anchor
                    candidate = [packet]
                    candidate_anchor = legacy._select_switch_anchor(
                        candidate,
                        normalizer.video_pids,
                    )
                elif candidate:
                    candidate.append(packet)
                    if candidate_anchor is None:
                        candidate_anchor = legacy._select_switch_anchor(
                            candidate,
                            normalizer.video_pids,
                        )

                if (
                    candidate_anchor is not None
                    and timeline._pts_at_or_after(candidate_anchor, target)
                    and len(candidate) >= timeline.MIN_SWITCH_CONTEXT_PACKETS
                ):
                    main.logger.info(
                        "TS-Proxy-Ersatzstrom am aktuellen Bild übernommen: Session=%s, Ziel=%s, Anker=%s, GelesenePakete=%s",
                        session_id,
                        target,
                        candidate_anchor,
                        read_packets,
                    )
                    return timeline._replacement_from_packets(
                        replacement.connection,
                        candidate,
                        normalizer,
                    )
    except (StopAsyncIteration, asyncio.TimeoutError):
        pass

    if candidate_anchor is not None and len(candidate) >= timeline.MIN_SWITCH_CONTEXT_PACKETS:
        newest_complete = candidate
        newest_anchor = candidate_anchor

    if newest_complete is not None and newest_anchor is not None:
        lag_seconds = ((target - newest_anchor) % legacy.PTS_WRAP) / 90_000
        main.logger.info(
            "TS-Proxy verwendet den neuesten verfügbaren Keyframe: Session=%s, Restabstand=%.2fs, Ursprungsabstand=%.2fs",
            session_id,
            lag_seconds,
            ((target - anchor) % legacy.PTS_WRAP) / 90_000,
        )
        return timeline._replacement_from_packets(
            replacement.connection,
            newest_complete,
            normalizer,
        )

    main.logger.warning(
        "TS-Proxy fand im kurzen Nachführfenster keinen neueren vollständigen Keyframe: Session=%s, Ziel=%s, Anker=%s",
        session_id,
        target,
        anchor,
    )
    return replacement


def install() -> None:
    timeline._catch_up_replacement = _catch_up_replacement_v3
