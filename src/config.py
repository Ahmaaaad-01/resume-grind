"""Load config.yaml and .env, validate required paths, ensure directories exist."""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


# Project root is one level up from src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PATHS = {
    "data/master_resume/resume_bank.json": (
        "Resume bank not found. Run:\n"
        "  cp examples/resume_bank.example.json "
        "data/master_resume/resume_bank.json\n"
        "Then edit it with your real experience."
    ),
    ".env": (
        "Environment file not found. Run:\n"
        "  cp .env.example .env\n"
        "Then add your API keys."
    ),
}

# Directories that must exist (auto-created)
REQUIRED_DIRS = [
    "data/master_resume",
    "data/resumes",
    "data/digests",
    "db",
]


def ensure_directories() -> None:
    """Create required data directories if they don't exist."""
    for dir_path in REQUIRED_DIRS:
        full_path = PROJECT_ROOT / dir_path
        full_path.mkdir(parents=True, exist_ok=True)


def check_setup(skip_resume_bank: bool = False) -> None:
    """Validate that required files exist. Exit with clear errors if not."""
    missing = False
    for rel_path, message in REQUIRED_PATHS.items():
        if skip_resume_bank and "resume_bank" in rel_path:
            continue
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            print(f"Missing: {rel_path}\n   {message}\n", file=sys.stderr)
            missing = True
    if missing:
        sys.exit(1)


def load_config(skip_validation: bool = False) -> dict:
    """
    Load configuration from config.yaml and .env.

    Returns the parsed config dict. Also loads environment variables
    from .env into os.environ.
    """
    ensure_directories()

    # Load .env into environment
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    if not skip_validation:
        check_setup()

    # Load config.yaml
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        print(f"Missing: config/config.yaml", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


def get_env(key: str) -> str:
    """Get a required environment variable or exit with an error."""
    value = os.environ.get(key)
    if not value:
        print(
            f"Missing environment variable: {key}\n"
            f"   Add it to your .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value
