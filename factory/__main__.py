"""python3 -m factory: build customized agent plugins from their upstreams."""
import argparse
import subprocess
import sys
from pathlib import Path

from . import audit, build, config, install, status
from .gitutil import GitError, git
from .new import clone_path, default_remote, new

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
        print(f"  main {r.main[:7]}, merged locally, not pushed")
        if r.audit_needed:
            print(f"  next: `audit {args.plugin}`, give every row a verdict, commit it on main, then `push {args.plugin}`")
        else:
            print(f"  next: `push {args.plugin}` (no new upstream build to audit)")
    return code


def _targets(args) -> list[str]:
    return [args.target] if args.target else list(config.load(args.root, args.plugin).targets)


def cmd_audit(args) -> int:
    code = 0
    for target in _targets(args):
        clone = clone_path(args.root, args.plugin, target)
        head = f"{args.plugin}/{target}"
        if not audit.needed(clone):
            print(f"{head}: upstream build already published; nothing to audit")
            continue
        path = audit.skeleton(clone)
        c = audit.check(clone)
        rows = len(audit.changes(clone, audit.published(clone), git(clone, "rev-parse", "refs/heads/upstream")))
        if c.complete:
            print(f"{head}: {path} complete ({rows} paths)")
        else:
            state = "not committed on main" if not c.found else \
                f"{len(c.pending)} without verdict, {len(c.missing)} without row, {len(c.extra)} out of range"
            print(f"{head}: {path} ({rows} paths): {state}")
            code = 1
    return code


def cmd_push(args) -> int:
    for target in _targets(args):
        c = build.push(args.root, args.plugin, target)
        print(f"{args.plugin}/{target}: pushed" + (f" with audit {c.path.name}" if c else ""))
    return 0


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

    s = sub.add_parser("sync", help="build from upstream and merge into main, locally")
    s.add_argument("plugin")
    s.add_argument("--target")
    s.add_argument("--ref", help="upstream git ref (default: plugin.toml ref)")
    s.set_defaults(func=cmd_sync)

    a = sub.add_parser("audit", help="write or check the audit of the unpublished upstream build")
    a.add_argument("plugin")
    a.add_argument("--target")
    a.set_defaults(func=cmd_audit)

    pu = sub.add_parser("push", help="push main and upstream; a new upstream build needs a complete audit")
    pu.add_argument("plugin")
    pu.add_argument("--target")
    pu.set_defaults(func=cmd_push)

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
