# PX4 SIH in-process attacks and IDS

This extension adds a small C++ fault injector and a small C++ rule IDS to PX4 v1.17.0 SITL. SIH generates the flight and sensor data inside PX4. The injector changes the simulated GPS/barometer publication data or publishes a test vehicle command; the IDS subscribes to `sensor_gps`, `sensor_baro`, and `vehicle_command`. The IDS does not read the simulator's `drone_ids_sim_control` scenario labels.

The recorded run and its concise evidence files are in [`../reports/px4-inproc/`](../reports/px4-inproc/). The 114.9-second ULog contains simulator labels, IDS events, GPS/barometer data, estimator position, ground truth, and vehicle commands. `events.csv` extracts the IDS events (`IDS_GPS`, `IDS_BARO`, `IDS_CMD`) and simulator-only labels (`SIM_ATK`).

## Rebuild

Requirements: Docker and network access for the first PX4 source clone. These commands were verified with the PX4 `px4io/px4-dev:v1.17.0` build image. From the project root:

```sh
docker run -d --name px4-ids-dev px4io/px4-dev:v1.17.0 sleep infinity
docker exec px4-ids-dev bash -lc 'git clone --depth 1 --branch v1.17.0 https://github.com/PX4/PX4-Autopilot.git /opt/PX4-Autopilot'
docker cp px4_extension/px4-v1.17.0-drone-ids.patch px4-ids-dev:/tmp/drone-ids.patch
docker exec px4-ids-dev bash -lc 'cd /opt/PX4-Autopilot && git apply /tmp/drone-ids.patch && make px4_sitl_default sihsim_quadx'
```

The patch is pinned to PX4 v1.17.0 (`d6f12ad1c4f70ad3230afd7d86e971421e02fef4`). Later PX4 releases may need patch updates. PX4's build tooling is used at compile time; Python is not used to inject attacks or run the IDS.

## Run and capture

```sh
docker exec -it px4-ids-dev bash -lc 'cd /opt/PX4-Autopilot/build/px4_sitl_default && PX4_SIM_MODEL=sihsim_quadx PX4_SIMULATOR=sihsim ./bin/px4'
```

At the PX4 `pxh>` prompt, enter `commander takeoff`. The custom SIH airframe starts both modules automatically. The deterministic scenario schedule is relative to module startup:

| Simulation time | Scenario | Injected observation | IDS evidence |
|---|---|---|---|
| 0–30 s | Baseline | None | No alert in the captured baseline interval |
| 30–42 s | GPS spoof | Position jump at simulated GPS publication; velocity remains unchanged | `IDS_GPS`, GPS position/velocity residual |
| 50–62 s | Barometer tampering | Pressure shifted by a 20 m-equivalent altitude bias | `IDS_BARO`, GPS/barometer altitude residual |
| 70–72 s | Command injection | External `MAV_CMD_USER_1` (31010) published with source system 42 | `IDS_CMD`, unauthorized command source |

This command is deliberately non-actuating. The simulation truth labels are `SIM_ATK` values 0 (none), 1 (GPS), 2 (barometer), and 3 (command). The IDS uses only sensor and command observations; it does not use these labels. The SIH airframe sets `SDLOG_PROFILE=33` so the normal topics and debug events are logged.

To find the resulting ULog inside the container:

```sh
find /opt/PX4-Autopilot/build/px4_sitl_default/rootfs/log -type f -name '*.ulg' -printf '%T@ %p\n' | sort -nr | head
```

Use `docker cp` to copy the selected log to the host. For optional post-run analysis, install `pyulog` and export topics, for example:

```sh
ulog2csv flight.ulg --output converted --messages debug_key_value,vehicle_command,vehicle_local_position,vehicle_local_position_groundtruth,sensor_gps,sensor_baro
```

## Scope and caveats

The SIH run exercises three controlled test vectors. The GPS injection changes estimator inputs and can cause substantial estimator position error; the test does not demonstrate safe recovery or a controlled waypoint mission. The command vector is a synthetic uORB command, not a packet sent through a MAVLink radio/network stack. This PX4 extension does not implement communication DoS, packet loss, firmware alteration, or cryptographic firmware verification.

The Python IDS and public UAVIDS-2025 benchmark are separate evaluation paths. Their scores are not combined with this PX4 SIH run and are not estimates of real-world flight performance.
