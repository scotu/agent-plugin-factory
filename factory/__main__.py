"""python3 -m factory: build customized agent plugins from their upstreams."""
import argparse
import subprocess
import sys
from pathlib import Path

from . import build, config, install, status
from .gitutil import GitError
from .new import default_remote, new

ROOT = Path(__file__).resolve().parent.parent


def cmd_sync(args) -> int:
    plugin = config.load(args.root, args.plugin)
    code = 0
    for target in [args.target] if args.target else list(plugin.targets):
        r = build.sync(args.root, args.plugin, target, args.ref)
        print(f"{args.plugin}/{target}: upstream {r.built[:7]} built from {r.upstream_sha[:12]}")
        for entry in r.reviews:
            print(f"  review {entry.title} (upstream changed its files)")
        if r.conflicts:
            print(f"  MERGE CONFLICT on main in {r.clone}:")
            for path in r.conflicts:
                print(f"    {path}")
            print(f"  Re-apply each affected entry's Intent from {build.LEDGER}, commit, then run sync again.")
            code = 1
            continue
        print(f"  main {r.main[:7]}, " + ("pushed" if r.pushed else f"NOT pushed: {r.push_error}"))
        if not r.pushed:
            code = 1
        if args.install and target == "hermes":
            for profile in install.update(args.profiles, plugin.targets[target].plugin_key, r.clone):
                print(f"  updated profile {profile}")
    return code


def cmd_new(args) -> int:
    github_repo = None if args.remote else f"{args.owner}/{args.plugin}-{args.target}"
    remote = args.remote or default_remote(args.owner, args.plugin, args.target)
    plugin_dir = new(args.root, args.plugin, args.target, args.upstream, remote,
                     github_repo=github_repo, public=not args.private)
    print(f"created {plugin_dir} and build repo {remote}")
    print(f"next: write {plugin_dir / args.target / 'port.py'}, then `python3 -m factory sync {args.plugin}`")
    return 0


def cmd_status(args) -> int:
    for line in status.lines(args.root, [args.plugin] if args.plugin else config.names(args.root), args.profiles):
        print(line)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m factory", description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    p.add_argument("--profiles", type=Path, default=install.DEFAULT_PROFILES, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sync", help="build from upstream, merge into main, push")
    s.add_argument("plugin")
    s.add_argument("--target")
    s.add_argument("--ref", help="upstream git ref (default: plugin.toml ref)")
    s.add_argument("--install", action="store_true", help="update Hermes profiles installed from the build clone")
    s.set_defaults(func=cmd_sync)

    n = sub.add_parser("new", help="create a plugin folder and its build repo")
    n.add_argument("plugin")
    n.add_argument("--upstream", required=True, help="git URL, optionally #subdir")
    n.add_argument("--target", default="hermes")
    n.add_argument("--owner", default="scotu")
    n.add_argument("--private", action="store_true")
    n.add_argument("--remote", help="existing empty build repo URL (skips creating it on GitHub)")
    n.set_defaults(func=cmd_new)

    st = sub.add_parser("status", help="show build state for every plugin")
    st.add_argument("plugin", nargs="?")
    st.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    args.root = args.root.resolve()
    try:
        return args.func(args)
    except (config.ConfigError, build.SyncError, GitError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or ""
        print(f"error: {exc}{(chr(10) + detail.strip()) if detail else ''}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
