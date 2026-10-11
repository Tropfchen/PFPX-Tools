def main():
    import argparse
    from datetime import datetime, timezone
    from pathlib import Path

    from .pwx_exporter import WeatherCompiler

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


if __name__ == "__main__":
    main()
