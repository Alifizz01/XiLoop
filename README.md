# HiLo — X-in-the-Loop, from software to hardware

**HiLo wires your controller to a simulated plant, runs the closed loop, and verifies your
requirements automatically.** Think *pytest for control loops*.

```
[ Device under test ] --command--> [ Plant model ]
        ^                               |
        └---------- measurement --------┘
              LoopEngine (fixed rate)
   CampaignRunner: testplan.yaml -> PASS/FAIL report
```

- **Device** = the thing you're testing — a Python controller today; emulated firmware
  (Renode/QEMU) and real boards over serial on the roadmap.
- **Plant** = the simulated system — an actuator, motor, battery, vehicle… write your own
  in ~15 lines.
- **Campaign** = a YAML test plan with requirements (rise time, overshoot, steady-state
  error…). HiLo runs the scenarios and emits a pass/fail report.

## Quick start
```bash
pip install -e .[dev]
python -m examples.actuator_pid.run     # run the demo campaign
pytest -q                               # run the test suite
```

```python
from hilo import PID, PIDDevice, ActuatorPlant, CampaignRunner

device = PIDDevice(PID(kp=2.0, ki=1.0, kd=0.05))   # the controller under test
plant  = ActuatorPlant()                            # the simulated system
result = CampaignRunner(device, plant).run("examples/actuator_pid/testplan.yaml")
print(result.summary())                             # ... PASS/FAIL per requirement
```

## Why
In-the-loop testing (SiL/PiL/HiL) is how industry verifies control software before touching
real hardware — but the established tools (dSPACE, NI, ECU-TEST) cost five to six figures.
Students, makers and small teams rebuild the same plumbing every project. HiLo is that
plumbing, done once, open-source.

## Roadmap
| Version | Adds | Status |
|---|---|---|
| v0.1 | Core engine, Device/Plant interfaces, telemetry, campaign runner, actuator example | ✅ this release |
| v0.2 | Live dashboard (plots, setpoint, tuning) | planned |
| v0.3 | SocketDevice → C/C++ firmware in Renode/QEMU (PiL) | planned |
| v0.4 | SerialDevice → real microcontroller (true HiL), PyPI release | planned |

## License
MIT — © Muhamad Alif Izzuwan Bin Ibrahim ([github.com/Alifizz01](https://github.com/Alifizz01))
