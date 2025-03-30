import csv

from datetime import datetime
from pathlib import Path

from src.modules import global_constants as cst


def write_file(wallet: str, chain: str, action: str, status: int):
    root_path = Path(__file__).resolve().parent.parent.parent
    fila_path = root_path / "results.csv"

    data = [
        {
            "Wallet": wallet,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Chain": chain,
            "Action": action,
            "Status": "SUCCESS" if status == 1 else "FAILURE",
        }
    ]

    with open(str(fila_path), "a", newline="") as file:
        writer = csv.DictWriter(file, cst.CSV_COLUMNS, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerows(data)
        file.close()
