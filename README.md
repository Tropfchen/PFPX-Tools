Libraries and CLI for creating PFPX Weather Files (pwx) and PFPX Tracks Files (ots).

## CLI Usage (Weather Only)

You can use the CLI to compile weather data into PFPX Weather Files (pwx).

Example use for grib for 26-05-20 12:00, with 3 forecasts, at 0, 3, 6 hours in future:

```bash
   pfpx-tools --product-time 26-05-20-12 \
              --grib data_0h.grib -d 0 \
              --grib data_3h.grib -d 3 \
              --grib data_6h.grib -d 6 \
              --output forecast.pwx
```

(in case of issues, replace `pfpx-tools` with `python -m pfpx-tools` or `uv run pfpx-tools`)

Options:

- `--product-time`: UTC / Zulu format (YY-MM-DD-HH)
- `--grib`, `-g`: Path to GRIB2 file (can be used multiple times)
- `--grib-delta`, `-d`: Forecast time for each GRIB file (one delta per file)
- `--metar`, `-m`: path (optional)
- `--taf`, `-t`: path (optional)
- `--output`, `-o`: Output file path (required)

## Libraries

- `WeatherCompiler`: For creating PFPX Weather Files (pwx).
- `TrackCompiler`: For creating PFPX Tracks Files (ots).

## Requirements

To use you need:

- For weather:

  - GRIB in GRIB2 binary format, with temperature, UGRD and VGRD parameters along with 10-1000 millibar levels.
    I recommend lowest resolution, the `1p00` - already higher than what PFPX subscription provides.
    Working Example of params:

    ```
    "lev_10_mb": "on", # ~30km / ~FL900
    "lev_50_mb": "on",
    "lev_100_mb": "on",
    "lev_200_mb": "on",
    "lev_250_mb": "on", #25,000Pa / ~10km / ~FL340
    "lev_300_mb": "on",
    "lev_400_mb": "on",
    "lev_500_mb": "on",
    "lev_700_mb": "on", # 700Pa / ~10km / ~FL340
    "lev_850_mb": "on",
    "lev_1000_mb": "on",
    "var_TMP": "on",
    "var_UGRD": "on",
    "var_VGRD": "on",
    "leftlon": "0",
    "rightlon": "360",
    "toplat": "90",
    "bottomlat": "-90"
    ```

  - TAF: optional
  - METAR: optional
