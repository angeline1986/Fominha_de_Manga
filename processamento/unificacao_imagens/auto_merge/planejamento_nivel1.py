"""Builds a Level I safe/partial plan from the existing V3 cut strategy."""
from dataclasses import asdict, dataclass

from processamento.unificacao_imagens import image_stitcher as v3


@dataclass(frozen=True)
class Interval:
    start: int
    end: int
    status: str
    reason: str


@dataclass(frozen=True)
class Level1Plan:
    status: str
    total_height: int
    intervals: tuple[Interval, ...]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "total_height": self.total_height,
            "intervals": [asdict(item) for item in self.intervals],
        }


def _bands_from(origin: int, bands: list) -> list:
    return [
        v3.WhiteBand(
            band.start - origin, band.end - origin,
            band.height, band.white_ratio_mean,
        )
        for band in bands
        if band.start >= origin
    ]


def _next_resume_boundary(start: int, total: int, bands: list) -> int | None:
    lower = start + v3.DEFAULT_MAX_CHUNK_HEIGHT
    upper = total - v3.DEFAULT_MIN_CHUNK_HEIGHT
    candidates = [
        (band.start + band.end) // 2
        for band in bands
        if band.height >= v3.DEFAULT_MIN_WHITE_BAND
        and lower < (band.start + band.end) // 2 <= upper
    ]
    return min(candidates) if candidates else None


def _choose_from(origin: int, total: int, bands: list) -> list[int]:
    cuts, _ = v3.choose_cuts(total - origin, _bands_from(origin, bands))
    return [origin + int(cut["center"]) for cut in cuts]


def plan_level1(total_height: int, bands: list) -> Level1Plan:
    """Plan safe intervals and residuals without rendering or writing files."""
    if type(total_height) is not int or total_height <= 0:
        raise ValueError("A altura total deve ser um inteiro positivo.")

    intervals: list[Interval] = []
    origin = 0
    while origin < total_height:
        boundaries = [origin, *_choose_from(origin, total_height, bands), total_height]
        oversized = next((
            (start, end) for start, end in zip(boundaries, boundaries[1:])
            if end - start > v3.DEFAULT_MAX_CHUNK_HEIGHT
        ), None)
        if oversized is None:
            intervals.extend(
                Interval(start, end, "safe", "v3_safe_segment")
                for start, end in zip(boundaries, boundaries[1:])
            )
            break

        blocked_start, blocked_end = oversized
        intervals.extend(
            Interval(start, end, "safe", "v3_safe_segment")
            for start, end in zip(boundaries, boundaries[1:])
            if end <= blocked_start
        )
        resume = _next_resume_boundary(blocked_start, total_height, bands)
        if resume is None:
            intervals.append(Interval(
                blocked_start, total_height, "pending", "no_safe_boundary_before_max_height",
            ))
            break
        intervals.append(Interval(
            blocked_start, resume, "pending", "no_safe_boundary_before_max_height",
        ))
        origin = resume

    safe_exists = any(item.status == "safe" for item in intervals)
    pending_exists = any(item.status == "pending" for item in intervals)
    status = "partial" if safe_exists and pending_exists else "unresolved" if pending_exists else "complete"
    plan = Level1Plan(status, total_height, tuple(intervals))
    validate_plan(plan)
    return plan


def validate_plan(plan: Level1Plan) -> None:
    """Reject gaps, overlaps, empty intervals, or unsafe materialization claims."""
    expected = 0
    for item in plan.intervals:
        if item.start != expected or item.end <= item.start:
            raise ValueError("O plano Nível I contém lacuna, sobreposição ou intervalo vazio.")
        if item.status == "safe" and item.end - item.start > v3.DEFAULT_MAX_CHUNK_HEIGHT:
            raise ValueError("O plano marcou como seguro um intervalo acima da altura máxima.")
        if item.status == "pending" and item.end - item.start <= v3.DEFAULT_MAX_CHUNK_HEIGHT:
            raise ValueError("O residual pendente não excede a altura máxima.")
        if item.status not in {"safe", "pending"}:
            raise ValueError("Estado de intervalo desconhecido.")
        expected = item.end
    if expected != plan.total_height:
        raise ValueError("O plano Nível I não cobre toda a altura da obra.")
