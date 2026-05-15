#!/usr/bin/env python
"""
Library for creating PFPX Weather Files (pwx).
"""

from __future__ import annotations

import re
import zlib
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Iterable, Iterator

WX_REGEX = re.compile(r"^(?:(TAF|METAR) )?(?P<icao>[A-Z0-9]{4}) \d{6}Z ")
HEADER_FILL = bytes([0x3F]) * 10
RETRO_AIRPORTS_PAIRS = {"EDDB": "EDDT", "VHHH": "VHHX"}
_WINDS_COMPRESSION = 1  # about 100% saving compared to store, higher is pointless
_WX_COMPRESSION = 3


class WeatherCompiler:
    """Compiles weather data into PFPX Weather File (pwx).
    GRIB needs to contain temperature, UGRD and VGRD parameters along with\
    10-1000 millibar levels and come in GRIB2 binary format.
    At least one GRIB has to be added before data can be compiled.
    TAF's and METAR's are optional.
    """

    def __init__(
        self,
        product_time_utc: datetime,
        product_expire_timedelta: timedelta = timedelta(days=2),
    ):
        """
        :param product_time_utc: Product datetime of GRIB data\
        (e.g. prod/gfs.20260501/12 date). Naive is treated as UTC.
        :param product_expire_timedelta: Validity time of weather data.\
        Defaults to 2 days. Effect on PFPX is unknown.
        """
        self.product_time = (
            product_time_utc.replace(tzinfo=timezone.utc)
            if product_time_utc.tzinfo is None
            else product_time_utc.astimezone(timezone.utc)
        )

        self.expire_time = self.product_time + product_expire_timedelta
        self.gribs = BytesIO()
        self._grib_count = 0

        self.add_metars([])
        self.add_tafs([])

    @staticmethod
    def _make_header(tag: str) -> bytes:
        return tag.encode() + HEADER_FILL

    @staticmethod
    def _build_footer() -> bytes:
        return b"<END>"

    @staticmethod
    def _format_expire(dt: datetime) -> str:
        return dt.strftime("%Y %m %d %H:%M")

    @staticmethod
    def _format_ref(dt: datetime) -> str:
        return dt.strftime("%Y%m%d%H")

    def add_grib(self, grib: bytes, forecast_delta: int) -> WeatherCompiler:
        """
        Add GRIB2 forecast data.
        GRIB needs to contain temperature, UGRD and VGRD parameters\
        along with levels at 10-1000 millibar.
        There are no checks for GRIB correctness.

        :param grib: GRIB2 binary data
        :type grib: bytes
        :param forecast_delta: Forecasted offset hour\
        (e.g. 3 for "pgrb2full.0p50.f003").
        :type forecast_delta: int
        :raises TypeError: If grib is not bytes or forecast_delta a number
        :raises ValueError: If grib is not a valid GRIB2 file or forecast_delta\
        out of range
        """
        if not isinstance(grib, bytes):
            raise TypeError("grib must be bytes")
        if not grib[:4] == b"GRIB":
            raise ValueError("Invalid GRIB2 file: missing GRIB header")
        if not (0 <= forecast_delta <= 99):  # 384 ?
            raise ValueError("Forecast delta must be in 0-99 hour range")
        if forecast_delta % 3 != 0:
            raise ValueError("Forecast delta must be a multiple of 3 hours")

        forecasted_time = self.product_time + timedelta(hours=forecast_delta)
        self.gribs.write(
            f"[DATA_{forecast_delta:02}]".encode()
        )  # GRIB_VALID_TIME - GRIB_REF_TIME
        self.gribs.write(
            forecasted_time.strftime("%Y%m%d%H%M").encode().hex().encode()
        )  # GRIB_VALID_TIME
        self.gribs.write(grib.hex().encode())

        self._grib_count += 1

        return self

    def _build_winds_block(self) -> bytes:
        header = self._make_header("<Winds>")

        body = BytesIO()
        body.write(f"Expires {self._format_expire(self.expire_time)}\n".encode())
        body.write(f"{self._format_ref(self.product_time)}\n".encode())
        body.write(self.gribs.getvalue())
        body.write(b"[DATA_ED]")

        body_bytes = body.getvalue()
        compressed = zlib.compress(
            body_bytes, level=_WINDS_COMPRESSION
        )  # GRIB2 comes already compressed
        return header + compressed

    def add_metars(self, metars: Iterable | dict[str, str]) -> WeatherCompiler:
        """
        WX input data format requirement is very relaxed, prefably it should be\
        dictionary of ``{"ICAO":"METAR ICAO timeZ (...)"}`` pairs.
        Otherwise any iterable that can match ``WX_REGEX`` will be accepted.
        """
        self.metars = self._build_wx_data_block("METAR", metars)
        return self

    def add_tafs(self, tafs: Iterable | dict[str, str]) -> WeatherCompiler:
        """
        WX input data format requirement is very relaxed, prefably it should be\
        dictionary of ``{"ICAO":"TAF ICAO timeZ (...)"}`` pairs.
        Otherwise any iterable that can match ``WX_REGEX`` will be accepted.
        """
        self.tafs = self._build_wx_data_block("TAF", tafs)
        return self

    def _build_wx_data_block(
        self,
        block_type: str,
        wx: Iterable | dict[str, str],
        fill_retro_airports_wx=True,
    ) -> bytes:
        header = self._make_header(f"<{block_type}>")

        body = BytesIO()
        body.write(f"Expires {self._format_expire(self.expire_time)}\n".encode())

        for station, value in self._parse_wx_data(wx):
            body.write(f"{station} {value}\r".encode())
            if fill_retro_airports_wx and station in RETRO_AIRPORTS_PAIRS:
                old = RETRO_AIRPORTS_PAIRS[station]
                body.write(f"{old} {value.replace(station, old)}\r".encode())

        body_bytes = body.getvalue()
        compressed = zlib.compress(body_bytes, level=_WX_COMPRESSION)
        return header + compressed

    def _parse_wx_data(
        self, wx: Iterable | dict[str, str]
    ) -> Iterator[tuple[str, str]]:
        if isinstance(wx, dict):
            for station, value in wx.items():
                normalized = self._normalize_wx_string(value)
                yield station, normalized
        else:
            try:
                for value in wx:
                    match = WX_REGEX.search(value)
                    if match:
                        station = match.group("icao")
                        normalized = self._normalize_wx_string(value)
                        yield station, normalized
            except TypeError as err:
                raise ValueError(
                    f"Invalid wx type: {type(wx)}. Expected dict or iterable."
                ) from err

    @staticmethod
    def _normalize_wx_string(value: str) -> str:
        return re.sub(r"[\t\n]", " ", re.sub(r"\s{2,}", " ", value.upper().strip()))

    def compile(self) -> bytes:
        """
        Compile weather data.
        """

        assert self._grib_count, "No GRIB data added. Call add_grib() first."

        output = BytesIO()
        output.write(self._build_winds_block())
        output.write(self.metars)
        output.write(self.tafs)
        output.write(self._build_footer())

        return output.getvalue()


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Compile weather data into PFPX Weather File (pwx)."
    )
    parser.add_argument(
        "--product-time",
        type=str,
        help="Product datetime in UTC / Zulu (YY-MM-DD-HH)",
    )
    parser.add_argument(
        "--grib",
        "-g",
        type=Path,
        required=True,
        action="append",
        help="Path to GRIB2 file",
    )
    parser.add_argument(
        "--grib-delta",
        "-d",
        type=int,
        required=True,
        action="append",
        help="Forecast delta in hours for the grib",
    )
    parser.add_argument("--metar", "-m", type=Path, help="METAR path")
    parser.add_argument("--taf", "-t", type=Path, help="TAF path")
    parser.add_argument(
        "--output", "-o", type=Path, required=True, help="Output file path"
    )

    args = parser.parse_args()
    output_path = Path(args.output).resolve()

    if len(args.grib) != len(args.grib_delta):
        print("You need to provide delta for each grib. Exiting")
        exit()

    if args.product_time:
        product_time = datetime.strptime(args.product_time, "%y-%m-%d-%H")  # noqa: DTZ007
    else:
        product_time = datetime.now(timezone.utc)
    compiler = WeatherCompiler(product_time)

    for grib_path, delta in zip(args.grib, args.grib_delta):
        with Path(grib_path).open("rb") as f:
            grib_data = f.read()
        compiler.add_grib(grib_data, delta)

    if args.metar:
        with Path(args.metar).open("r", encoding="utf-8") as f:
            compiler.add_metars(f.read())

    if args.taf:
        with Path(args.taf).open("r", encoding="utf-8") as f:
            compiler.add_tafs(f.read())

    output_data = compiler.compile()
    output_path.write_bytes(output_data)
