import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reboot te server on code changes",
    )
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=args.reload,
    )

if __name__ == "__main__":
    main()