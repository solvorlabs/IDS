# Data sources and provenance

## Bundled: UAVIDS-2025

- Record: [Zenodo 10.5281/zenodo.15336998](https://zenodo.org/records/15336998)
- Authors: Qingli Zeng, Abdalrahman Bashir, Farid Nait-Abdesselam
- License: Creative Commons Attribution 4.0 International (CC BY 4.0), as declared in the Zenodo record.
- Generator: NS-3.24 UAV swarm/network simulation with extended BOID mobility.
- Coverage: 122,171 labeled network flows, five classes (Normal, Blackhole, Flooding, Sybil, Wormhole), 22 columns including identifiers and labels.
- Bundled path: `data/external/UAVIDS-2025.csv`
- SHA-256: `d50d339f68be7b23f0bf089dd438b20a1835c13182d8641220538121440164d0`
- The benchmark intentionally excludes `FlowID`, `SrcAddr`, and `DstAddr` from model features. Protocol and port fields are not used by the numeric baseline.
- Please retain this attribution and the CC BY 4.0 terms when reusing the source data.

## Considered, not bundled: PX4/Gazebo GPS Spoofing Dataset

- Repository: [anthony-finn/UAV-GPS-Spoofing-Dataset](https://github.com/anthony-finn/UAV-GPS-Spoofing-Dataset)
- The repository describes PX4 SITL/Gazebo Classic trajectories with normal and incrementally spoofed GPS readings plus IMU, barometer, magnetometer, and ground-truth streams.
- Its linked archive is approximately 2.4 GB. The repository API reports no declared license. It is therefore not redistributed or included in benchmark results here.
- The generated `gps_spoof` scenario in this project is an independent, explicit synthetic case—not copied from or claimed to reproduce this source.

## Synthetic dataset created by this project

Generated with the documented deterministic equations in `src/drone_ids/synthetic.py`. It is derived from no third-party flight recordings. Every generated row includes `run_id`, `seed`, `scenario`, timestamps, observed channels, simulator-only truth columns, and an evaluation label. The IDS feature whitelist is explicit and excludes labels, truth, and injected attack metadata.

The workspace project does not yet include a separate license for its original code or generated dataset. Do not infer a license from the source-data license.
