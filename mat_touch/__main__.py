from . import config


def main() -> None:
    cfg = config.load()
    # TODO(M1): start the Tkinter wizard (app.py).
    print(f"mat-touch: config {config.CONFIG_PATH}\n{cfg}")


if __name__ == "__main__":
    main()
