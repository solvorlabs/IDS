# UAV Drone Intrusion Detection System

An interpretable intrusion detection prototype for simulated UAV sensor streams and UAV swarm network traffic. The repository includes a deterministic sensor-data generator, a streaming rule-based IDS, an evaluation pipeline, and a PX4 Software-In-The-Loop (SIH) integration.

## Capabilities

- Generate reproducible flight and sensor traces with six labeled scenarios: normal operation, GPS spoofing, command injection, telemetry tampering, communication denial of service, and firmware-integrity anomalies.
- Run an interpretable streaming IDS that reports alert time, rule, observed value, threshold, severity, and explanation.
- Evaluate a separate network-flow baseline on the public UAVIDS-2025 dataset.
- Run C++ fault injection and IDS modules inside a custom PX4 v1.17.0 SIH/SITL build. The captured SIH run covers GPS position spoofing, barometer tampering, and an unauthorized non-actuating vehicle command.

All generated flight data is synthetic. PX4 SIH attack injection and detection run inside PX4 without Gazebo or an external Python runtime. Python is used for the data generator, analysis pipeline, tests, and optional post-run ULog conversion.

## Quick start

Requires Python 3.10 or later. The generator, IDS, benchmark, and tests use the Python standard library.

```sh
python -m src.drone_ids.cli all --out reports/latest
python -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
python -m src.drone_ids.cli all --out reports\latest
python -m unittest discover -s tests -v
```

`all` generates 120 deterministic runs (20 per scenario), evaluates the sensor IDS, benchmarks UAVIDS-2025, and writes an HTML report with metrics and alert summaries. The default seed is `20260927`.

To generate a standalone dataset:

```sh
python -m src.drone_ids.cli generate --out data/generated/synthetic_uav_ids.csv --runs 120 --duration 120 --rate 5 --seed 20260927
```

## PX4 SIH

The custom PX4 modules inject faults at the simulated GPS and barometer publication boundaries and publish a controlled test command. The IDS monitors PX4 sensor and vehicle-command topics; it does not consume simulator labels. Build instructions, scenario timing, and scope are in [`px4_extension/README.md`](px4_extension/README.md). The PX4 v1.17.0 source changes are provided as [`px4_extension/px4-v1.17.0-drone-ids.patch`](px4_extension/px4-v1.17.0-drone-ids.patch).

The captured 114.9-second SIH run is [`reports/px4-inproc/px4_sih_inprocess_takeoff.ulg`](reports/px4-inproc/px4_sih_inprocess_takeoff.ulg). Its summarized detections are in [`reports/px4-inproc/events.csv`](reports/px4-inproc/events.csv), with run metadata in [`reports/px4-inproc/summary.json`](reports/px4-inproc/summary.json). The ULog is 24.6 MB; selected topics can be re-exported with `pyulog` as described in the PX4 guide.

## Results

The generated report is available at [`reports/latest/index.html`](reports/latest/index.html). Machine-readable metrics are in `reports/latest/synthetic/synthetic_metrics.json` and `reports/latest/public/uavids_2025_metrics.json`.

The synthetic evaluation measures the IDS on controlled scenarios generated from the same documented signal model. It does not estimate performance on real flights. UAVIDS-2025 contains network-flow data and evaluates a separate network classifier; it does not validate the sensor IDS.

## Repository layout

```text
data/external/       Attributed UAVIDS-2025 data
data/generated/      Reproducible synthetic sensor dataset and manifest
px4_extension/       PX4 patch and SIH build/run guide
reports/latest/      Evaluation report and machine-readable metrics
reports/px4-inproc/  PX4 SIH ULog and IDS event summary
src/drone_ids/       Generator, IDS, metrics, CLI, and SIH adapter
tests/               Unit tests
```

## Data attribution

The bundled UAVIDS-2025 data is distributed under CC BY 4.0. Its source, attribution, checksum, and coverage are documented in [`DATA_SOURCES.md`](DATA_SOURCES.md). The original project code and generated dataset do not currently have a separate license declaration.

## Limitations

- Synthetic evaluations use controlled signals and assumptions shared with the detector; they are not field-performance estimates.
- The PX4 extension demonstrates three controlled SIH test vectors. Its command test is an internal uORB event, not a command sent over a MAVLink radio link.
- The PX4 extension does not implement network DoS or runtime firmware-integrity verification.
- No physical aircraft, operational mission, or safety response is evaluated.
