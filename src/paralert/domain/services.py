from .models import WindData


def find_calm_hours(wind_data: WindData, threshold_kmh: float, date: str) -> tuple[int, ...]:
    """
    Returns UTC hours where wind speed <= threshold at ALL configured altitudes.
    An hour is calm only if every altitude level satisfies the condition.
    """
    hours_per_altitude: list[set[int]] = []
    for altitude, hourly in wind_data.hourly.items():
        calm = {
            int(dt.split("T")[1].split(":")[0])
            for dt, speed in hourly.items()
            if dt.startswith(date) and speed <= threshold_kmh
        }
        hours_per_altitude.append(calm)

    if not hours_per_altitude:
        return ()

    calm_all = hours_per_altitude[0]
    for s in hours_per_altitude[1:]:
        calm_all &= s

    return tuple(sorted(calm_all))


def max_wind_on_date(wind_data: WindData, date: str) -> float:
    """Max wind speed across all altitudes for a given date."""
    speeds = [
        speed
        for hourly in wind_data.hourly.values()
        for dt, speed in hourly.items()
        if dt.startswith(date)
    ]
    return max(speeds) if speeds else 0.0
