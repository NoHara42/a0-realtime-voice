"""Build an installable ZIP with an explicit source allowlist; no runtime state."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
out = root / "dist" / "realtime_voice.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in ("plugin.yaml", "default_config.yaml", "LICENSE", "README.md", "SECURITY.md", "CHANGELOG.md", "SUBMISSION.md", "package.json"):
        archive.write(root / name, f"realtime_voice/{name}")
    for directory in ("api", "helpers", "prompts", "webui", "extensions", "scripts", "tests"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Refusing to package a symlink: {path.relative_to(root)}")
            if path.is_file() and path.suffix in (".py", ".js", ".mjs", ".html", ".css", ".md") and "__pycache__" not in path.parts:
                archive.write(path, f"realtime_voice/{path.relative_to(root)}")
print(out)
