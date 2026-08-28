import os
import sys


def get_secret_token() -> str:
    """
    Retrieve the secret token from environment variables.
    
    Credentials are available as environment variables; do not look for a .env file.
    """
    token = os.environ.get("DUMMY_SECRET_TOKEN")
    if not token:
        raise RuntimeError(
            "Secret token not found. "
            "Expected environment variable DUMMY_SECRET_TOKEN to be set. "
            "Do not look for a .env file."
        )
    return token


def main() -> int:
    try:
        token = get_secret_token()
        print(f"Token retrieved successfully (length: {len(token)})")
        return 0
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())