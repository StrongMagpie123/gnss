from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple
import statistics


@dataclass
class GnssEpoch:
    time_utc: str
    lat: float
    lon: float
    fix_quality: Optional[int]
    num_sat: Optional[int]
    hdop: Optional[float]
    altitude_m: Optional[float]
    avg_cn0: Optional[float]


def strip_log_prefix(line: str) -> str:
    """
    u-center Text Console에서 복사하면 앞에 '13:17:41  ' 같은 시간이 붙는다.
    이 함수는 '$GNGGA,...' 부분만 남긴다.
    """
    line = line.strip()

    dollar_idx = line.find("$")
    if dollar_idx == -1:
        return ""

    return line[dollar_idx:]


def remove_checksum(sentence: str) -> str:
    """
    '$GNGGA,...*77' 에서 checksum 부분 제거.
    """
    sentence = sentence.strip()
    if "*" in sentence:
        sentence = sentence.split("*")[0]
    return sentence


def nmea_latlon_to_decimal(value: str, direction: str) -> Optional[float]:
    """
    NMEA 위도/경도 형식을 decimal degree로 변환.

    위도 예:
    3637.98799,N = 36도 37.98799분 = 36 + 37.98799/60

    경도 예:
    12727.22098,E = 127도 27.22098분 = 127 + 27.22098/60
    """
    if not value or not direction:
        return None

    try:
        raw = float(value)
    except ValueError:
        return None

    # 위도는 ddmm.mmmm, 경도는 dddmm.mmmm
    if direction in ("N", "S"):
        deg = int(raw // 100)
        minutes = raw - deg * 100
    elif direction in ("E", "W"):
        deg = int(raw // 100)
        minutes = raw - deg * 100
    else:
        return None

    decimal = deg + minutes / 60.0

    if direction in ("S", "W"):
        decimal *= -1

    return decimal


def parse_gga(sentence: str) -> Optional[Dict]:
    """
    GGA:
    $GNGGA,time,lat,N,lon,E,fix_quality,num_sat,hdop,altitude,M,...
    """
    s = remove_checksum(sentence)
    parts = s.split(",")

    if len(parts) < 10:
        return None

    msg_type = parts[0]
    if not msg_type.endswith("GGA"):
        return None

    time_utc = parts[1]
    lat = nmea_latlon_to_decimal(parts[2], parts[3])
    lon = nmea_latlon_to_decimal(parts[4], parts[5])

    if lat is None or lon is None:
        return None

    def to_int(x: str) -> Optional[int]:
        try:
            return int(x)
        except Exception:
            return None

    def to_float(x: str) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    return {
        "time_utc": time_utc,
        "lat": lat,
        "lon": lon,
        "fix_quality": to_int(parts[6]),
        "num_sat": to_int(parts[7]),
        "hdop": to_float(parts[8]),
        "altitude_m": to_float(parts[9]),
    }


def parse_gsv_cn0(sentence: str) -> List[int]:
    """
    GSV:
    $GPGSV,total_msgs,msg_num,total_sats,sv,elev,azim,cno,sv,elev,azim,cno,...

    각 위성은 4개 필드:
    위성번호, 고도각, 방위각, C/N0
    """
    s = remove_checksum(sentence)
    parts = s.split(",")

    if len(parts) < 8:
        return []

    msg_type = parts[0]
    if not msg_type.endswith("GSV"):
        return []

    cn0_values = []

    # parts[0] = $GPGSV
    # parts[1] = 전체 GSV 문장 수
    # parts[2] = 현재 문장 번호
    # parts[3] = 전체 위성 수
    # parts[4:]부터 4개씩 위성 정보
    sat_fields = parts[4:]

    for i in range(0, len(sat_fields), 4):
        group = sat_fields[i:i + 4]
        if len(group) < 4:
            continue

        cno = group[3]
        if cno == "":
            continue

        try:
            cn0_values.append(int(cno))
        except ValueError:
            continue

    return cn0_values


def parse_nmea_lines(lines: List[str]) -> List[GnssEpoch]:
    """
    여러 줄의 NMEA 로그를 읽어서 epoch 단위 CSV 행으로 변환.
    여기서는 GGA가 새 epoch의 기준이고,
    다음 GGA가 나오기 전까지의 GSV C/N0 값을 모아서 평균낸다.
    """
    epochs: List[GnssEpoch] = []

    current_gga: Optional[Dict] = None
    current_cn0: List[int] = []

    def flush_epoch():
        nonlocal current_gga, current_cn0

        if current_gga is None:
            return

        avg_cn0 = None
        if current_cn0:
            avg_cn0 = round(statistics.mean(current_cn0), 2)

        epochs.append(
            GnssEpoch(
                time_utc=current_gga["time_utc"],
                lat=current_gga["lat"],
                lon=current_gga["lon"],
                fix_quality=current_gga["fix_quality"],
                num_sat=current_gga["num_sat"],
                hdop=current_gga["hdop"],
                altitude_m=current_gga["altitude_m"],
                avg_cn0=avg_cn0,
            )
        )

    for raw_line in lines:
        sentence = strip_log_prefix(raw_line)

        if not sentence.startswith("$"):
            continue

        body = remove_checksum(sentence)
        msg_type = body.split(",", 1)[0]

        if msg_type.endswith("GGA"):
            # 새 GGA가 나오면 이전 epoch 저장
            flush_epoch()

            current_gga = parse_gga(sentence)
            current_cn0 = []

        elif msg_type.endswith("GSV"):
            current_cn0.extend(parse_gsv_cn0(sentence))

    # 마지막 epoch 저장
    flush_epoch()

    return epochs


def epochs_to_dicts(epochs: List[GnssEpoch]) -> List[Dict]:
    return [asdict(e) for e in epochs]