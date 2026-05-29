"""Gmail OAuth2 token generator utility.

This standalone utility performs the Gmail OAuth2 consent flow and saves
the resulting token locally for use by the Notification System.

Usage:
    python src/create_token.py
    python src/create_token.py --client-secrets path/to/secrets.json --token-output path/to/token.json
"""

import argparse
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail send scope - the only permission needed for sending emails
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def generate_token(client_secrets_path: str, token_output_path: str) -> None:
    """Run the OAuth2 consent flow and save the resulting token.

    Args:
        client_secrets_path: Path to the Gmail OAuth2 client secrets JSON file.
        token_output_path: Path where the resulting token will be saved.

    Raises:
        FileNotFoundError: If the client secrets file does not exist.
        Exception: If the OAuth2 flow fails or is cancelled.
    """
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_output_path, "w") as token_file:
        token_file.write(creds.to_json())

    print(f"Token saved to {token_output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Gmail OAuth2 token for the River Level Notification System."
    )
    parser.add_argument(
        "--client-secrets",
        default="gmail_credentials.json",
        help="Path to the Gmail OAuth2 client secrets file (default: gmail_credentials.json)",
    )
    parser.add_argument(
        "--token-output",
        default="token.json",
        help="Path to save the generated token (default: token.json)",
    )
    args = parser.parse_args()

    try:
        generate_token(args.client_secrets, args.token_output)
    except FileNotFoundError:
        print(f"Error: Client secrets file not found: {args.client_secrets}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during OAuth2 flow: {e}", file=sys.stderr)
        sys.exit(1)
