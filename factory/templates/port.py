"""Port hook for {{NAME}} on {{TARGET}}: fill `out` (empty apart from .git) from the upstream tree in `src`.

`ctx` has: plugin, target, here (this folder, for overlay files), upstream_sha, ref, and `version`,
which you may set so build commits read "{{NAME}} <version> @ <sha>".
"""
import json
import shutil


def port(src, out, ctx):
    shutil.copytree(src, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if not (out / "plugin.json").exists():
        manifest = {"name": "{{NAME}}", "version": f"0.0.0+{ctx.target}.{ctx.upstream_sha[:7]}"}
        (out / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
