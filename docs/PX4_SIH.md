# PX4 SIH integration

PX4 SIH is a practical flight-stack simulator for this IDS project: PX4 SITL and the simple in-process SIH physics model produce flight and sensor telemetry without a Gazebo world. It supplies vehicle motion and simulated IMU, GPS, barometer, and magnetometer data. It does not model radio propagation, cameras, or network attacks by itself.

## Verified in-process SIH run

The workspace contains a custom build based on PX4 v1.17.0. Two C++ PX4 modules are enabled on the SITL board: `drone_ids_sim` applies deterministic fault injections and `drone_ids` monitors uORB observations. Neither requires a Python process or Gazebo at run time. The PX4 build itself uses PX4's normal build toolchain. The simulation scheduler writes labels to `debug_key_value`, while IDS alerts use the same log topic under different keys. The IDS does not subscribe to the label topic.

Evidence is under `reports/px4-inproc/`:

- `px4_sih_inprocess_takeoff.ulg`: 114.9-second PX4 SIH takeoff and fault-injection run.
- `topics/`: extracted debug labels/alerts, commands, GPS, barometer, estimated local position, and SIH ground truth.
- `px4_sih_inprocess_stationary.ulg`: earlier in-process stationary run.

In the takeoff log, attack windows begin at 30 seconds (GPS), 50 seconds (barometer), and 70 seconds (command). IDS alert records show GPS position/velocity residuals of 49.70 m at injection and 50.17 m when the spoof clears; a GPS/barometer altitude residual of 21.10 m; and an unauthorized command from source system 42. The ULog contains `MAV_CMD_USER_1` (31010), intentionally chosen as a non-actuating test command. The local position estimate moved substantially under the GPS jump; this verifies a sensor-to-estimator effect but is not a controlled waypoint mission or evidence of safe response.

The data is fully SIH-generated. `pyulog` was used only after the run to export selected ULog topics. Reproduce the custom build and test in `px4_extension/README.md`.

## Reproduce

Follow `px4_extension/README.md`: check out PX4 v1.17.0, apply `px4_extension/px4-v1.17.0-drone-ids.patch`, build `px4_sitl_default`, and launch the `sihsim_quadx` binary in PX4's build container or a Linux PX4 build environment. The working v1.17.0 command is `make px4_sitl_default sihsim_quadx`; the newer `px4_sitl_sih` target is not present in this pinned release. Takeoff is commanded from the PX4 shell after startup. PX4 records the `.ulg` automatically.

## Data boundaries and limitations

The importer uses `vehicle_local_position` as an estimator/odometry-like observation and `vehicle_local_position_groundtruth` only in fields excluded from detector inputs. GPS is transformed to a local frame. The output carries the common IDS schema so the same rules can run on SIH observations and generated scenarios.

The earlier `reports/sih-smoke/` dataset remains an offline mutation of a stock-firmware trace. The custom in-process implementation adds only three test vectors: GPS spoofing at the simulated GPS sensor publication boundary, barometer pressure tampering at its publication boundary, and an unauthorized non-actuating `vehicle_command` event. It does not inject through a radio/MAVLink transport, model packet loss or DoS, alter the firmware image at runtime, or establish cryptographic firmware integrity. Do not generalize this limited prototype as coverage of every PS3 threat or as real-world performance.
