# utils.py

def minutes_to_hhmm(minutes):
    minutes = int(round(minutes))
    sign = "-" if minutes < 0 else ""
    minutes = abs(minutes)
    h = minutes // 60
    m = minutes % 60
    return f"{sign}{h:02d}:{m:02d}"


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default