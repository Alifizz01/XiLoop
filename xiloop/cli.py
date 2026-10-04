"""xiloop command line.

    xiloop run plan.yaml [--report report.md] [--csv DIR]   run a campaign; exit 1 on FAIL (CI)
    xiloop studio                                           open the desktop GUI
    xiloop serve [--port 8765]                              REST API + Studio in a browser
    xiloop firmware [--port 5555]                           virtual board for PiL trials
"""
import argparse
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xiloop", description="X-in-the-Loop test bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a test plan (needs plant:/device: sections)")
    r.add_argument("plan")
    r.add_argument("--report", help="write a Markdown report here")
    r.add_argument("--csv", help="write one telemetry CSV per scenario into this folder")
    s = sub.add_parser("serve", help="REST API + Studio on localhost")
    s.add_argument("--port", type=int, default=8765)
    g = sub.add_parser("studio", help="desktop GUI")
    g.add_argument("--port", type=int, default=8765)
    f = sub.add_parser("firmware", help="virtual board speaking the device protocol")
    f.add_argument("--port", type=int, default=5555)
    a = ap.parse_args(argv)

    if a.cmd == "run":
        from xiloop.campaign import CampaignRunner
        runner = CampaignRunner.from_plan(a.plan)
        result = runner.run(a.plan)
        getattr(runner.engine.device, "close", lambda: None)()
        print(result.summary())
        if a.report:
            result.to_markdown(a.report)
        if a.csv:
            os.makedirs(a.csv, exist_ok=True)
            for name, run in result.runs.items():
                run.to_csv(os.path.join(a.csv, f"{name}.csv"))
        return 0 if result.passed else 1
    if a.cmd == "serve":
        from xiloop.server import serve
        serve(a.port)
    elif a.cmd == "studio":
        from xiloop.studio_app import main as studio
        studio(a.port)
    elif a.cmd == "firmware":
        from xiloop.firmware import serve
        serve(a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
