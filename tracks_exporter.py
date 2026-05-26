"""
Library for creating PFPX Tracks Files (ots).
"""

from __future__ import annotations

import json
import re
import zlib
from datetime import datetime

HEADER_FILL = bytes([0x3F]) * 10


class TrackCompiler:
    """
    Compiles NAT and PACOTS tracks into PFPX OTS Tracks File.
    NAT have to be wrapped in between ()
    """

    re.compile(r"END OF PART ONE OF [ONE|TWO|THREE] PARTS$")
    re.compile(r"^NAT-\d")

    def __init__(self, expire_date: datetime, nat: str = "", pacots: str = ""):
        expire = expire_date.strftime("%Y %m %d %H:%M")
        self.tracks = f"Expires {expire}\n[NAT]\n{nat}\n[PACOTS]\n{pacots}\n[AUSOTS]"

    def __str__(self):
        return self.tracks

    def __bytes__(self) -> bytes:
        return HEADER_FILL + zlib.compress(self.tracks.encode(), level=0)


def extract_pacots(notam):
    if isinstance(notam, str):
        notam = json.loads(notam)
    paths = ""
    rtp = "%m/%d/%Y %H%M"
    wtp = "%d %b %H:%M %Y"
    for msg in notam["notamList"]:
        start_date = datetime.strptime(msg["startDate"], rtp).strftime(wtp)  # noqa: DTZ007
        end_date = datetime.strptime(msg["endDate"], rtp).strftime(wtp)  # noqa: DTZ007
        issue_date = datetime.strptime(msg["issueDate"], rtp).strftime(wtp)  # noqa: DTZ007
        end_msg = f"{start_date} UNTIL {end_date}. CREATED: {issue_date}".upper()

        icao_message = msg["icaoMessage"].split("E)")[1].strip().replace("\r\n", "\n")
        if icao_message.startswith("TDM"):
            # icao_message = re.sub(r'(?:[^\s]+\s){3}[^\s]+', lambda m: m.group(0) + '\n', icao_message)
            icao_message = re.sub(r" ((RMK|RTS)/)", r"\n\1", icao_message)
            icao_message = re.sub(r"((?:[^ ]* ){3}[^ ]*) ", r"\1 \n", icao_message)

            paths += f"{msg['notamNumber']} - ({icao_message}). {end_msg}\n \r\n"
        else:
            paths += f"{msg['notamNumber']} - {icao_message}. {end_msg}\r\n"

    return paths


def extract_nat(msgs):
    if isinstance(msgs, str):
        msgs = json.loads(msgs)

    end = datetime.fromisoformat(msgs[-1]["end_datetime"][:-1])
    paths = ""
    for part in msgs:
        # paths += f"{part['last_updated']} {part['accountability_id']} - ({part['condition_message']})\n"
        cm = part["condition_message"].replace("\r", "")
        paths += f"({cm})\n\n\n"
    return (end, paths)


