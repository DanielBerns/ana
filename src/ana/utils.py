from pathlib import Path
import yaml

def read_yaml(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}

    with open(file_path, "r") as f:
        content = yaml.safe_load(f)

    return content
