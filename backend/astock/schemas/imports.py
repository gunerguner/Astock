from enum import Enum


class ImportDataset(str, Enum):
    turnover = "turnover"
    point = "point"
    stock = "stock"
    global_assets = "global_assets"
    all = "all"
