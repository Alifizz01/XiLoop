# XiLoop — X-in-the-Loop, from software to hardware

**XiLoop wires your controller to a simulated plant, runs the closed loop, and verifies your
requirements automatically.** Think *pytest for control loops*.

```
[ Device under test ] --command--> [ Plant model ]
        ^                               |
        +---------- measurement --------+
              LoopEngine (fixed rate)
   CampaignRunner: testplan.yaml -> PASS/FAIL report
```

- **Device** = the thing you're testing — a Python controller today; emulated firmware
  (Renode/QEMU) and real boards over serial on the roadmap.
- **Plant** = the simulated system — an actuator, motor, battery, vehicle… write your own
  in ~15 lines.
- **Campaign** = a YAML test plan with requirements (rise time, overshoot, steady-state
  error…). XiLoop runs the scenarios and emits a pass/fail report.

## Quick start
```bash
pip install -e .[dev]
python -m examples.actuator_pid.run     # run the demo campaign
pytest -q                               # run the test suite
```

```python
from xiloop import PID, PIDDevice, ActuatorPlant, CampaignRunner

device = PIDDevice(PID(kp=2.0, ki=1.0, kd=0.05))   # the controller under test
plant  = ActuatorPlant()                            # the simulated system
result = CampaignRunner(device, plant).run("examples/actuator_pid/testplan.yaml")
print(result.summary())                             # ... PASS/FAIL per requirement
```

## Why
In-the-loop testing (SiL/PiL/HiL) is how industry verifies control software before touching
real hardware — but the established tools (dSPACE, NI, ECU-TEST) cost five to six figures.
Students, makers and small teams rebuild the same plumbing every project. XiLoop is that
plumbing, done once, open-source.

## How it compares

The pieces of this workflow exist — the combination doesn't:

| Existing tool | Great at | What XiLoop adds / does differently |
|---|---|---|
| [OpenHTF](https://github.com/google/openhtf) (Google) | Hardware test campaigns, measurements, pass/fail | OpenHTF orchestrates *bench tests on physical devices* — no closed control loop, no plant model. XiLoop closes the loop against a simulated plant. |
| [python-control](https://python-control.readthedocs.io), [bdsim](https://github.com/petercorke/bdsim) | Control-systems analysis & block-diagram simulation | Analysis libraries — no requirements-as-YAML, no pass/fail reports, no device-under-test abstraction toward firmware/hardware. |
| PX4 / ArduPilot SITL | Superb simulation-in-the-loop | Locked to their own flight stacks. XiLoop is domain-neutral: any plant, any controller. |
| [Renode](https://renode.io) / QEMU | Firmware emulation | They emulate the *chip*; no plant, no campaigns. XiLoop orchestrates around them (roadmap v0.3). |
| dSPACE / NI / Speedgoat / ECU-TEST | Certified, industrial HiL | Five-to-six-figure commercial rigs. XiLoop is the free, software-first on-ramp — not a certification replacement. |
| Hand-rolled scripts | Quick start | Rewritten badly every project. XiLoop is that plumbing, done once. |

One line: **pytest for control loops.**

## Roadmap
| Version | Adds | Status |
|---|---|---|
| v0.1 | Core engine, Device/Plant interfaces, telemetry, campaign runner, actuator example | ✅ this release |
| v0.2 | Live dashboard (plots, setpoint, tuning) | planned |
| v0.3 | SocketDevice → C/C++ firmware in Renode/QEMU (PiL) | planned |
| v0.4 | SerialDevice → real microcontroller (true HiL), PyPI release | planned |

## License
MIT — © Muhamad Alif Izzuwan Bin Ibrahim ([github.com/Alifizz01](https://github.com/Alifizz01))
