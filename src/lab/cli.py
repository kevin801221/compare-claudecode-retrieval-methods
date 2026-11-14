"""指令列入口：uv run lab <collect|check|build|closed|run|report>。"""
from __future__ import annotations

import argparse

from lab.common import FRAMEWORKS


def _model_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default="haiku")
    p.add_argument("--effort", default="medium")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=180)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lab", description="比較資料整理方式對 Claude Code 檢索準確度的影響")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="下載官方文件到 world/")
    c.add_argument("--only", nargs="+", choices=FRAMEWORKS, help="只下載部分框架（試跑用 agent-sdk）")
    c.add_argument("--force", action="store_true", help="覆寫既有的 world/docs.json")

    sub.add_parser("check", help="檢查 world/questions.json 的題目")

    b = sub.add_parser("build", help="建立 A/B/C 三組實驗資料夾")
    b.add_argument("--model", default="sonnet", help="盲建索引用的模型")

    _model_args(sub.add_parser("closed", help="閉卷對照：不給文件，每題問一次"))

    r = sub.add_parser("run", help="跑評測（可以續跑）")
    r.add_argument("--rounds", type=int, required=True, help="跑到第幾輪為止；已經完成的會跳過")
    _model_args(r)

    p = sub.add_parser("report", help="產生統計表與網頁資料")
    p.add_argument("--model", default="haiku")
    p.add_argument("--effort", default="medium")

    args = parser.parse_args(argv)
    if args.cmd == "collect":
        from lab.collect import collect
        collect(only=args.only, force=args.force)
    elif args.cmd == "check":
        from lab.world import check
        check()
    elif args.cmd == "build":
        from lab.build import build
        build(model=args.model)
    elif args.cmd == "closed":
        from lab.run import run_closed
        run_closed(model=args.model, effort=args.effort, workers=args.workers, timeout=args.timeout)
    elif args.cmd == "run":
        from lab.run import run
        run(rounds=args.rounds, model=args.model, effort=args.effort, workers=args.workers,
            timeout=args.timeout)
    elif args.cmd == "report":
        from lab.report import report
        report(model=args.model, effort=args.effort)
