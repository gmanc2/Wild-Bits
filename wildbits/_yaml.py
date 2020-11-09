# pylint: disable=bad-continuation
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Union

import oead
import pymsyt
from oead.aamp import get_default_name_table


class Msbt:
    _msyt: str
    _be: bool

    def __init__(self, file: Path):
        with NamedTemporaryFile(mode="wb", suffix=".msyt", delete=False) as tmp:
            pymsyt.export(file, tmp.name)
        self._msyt = Path(tmp.name).read_text("utf-8")
        if not self._msyt:
            raise ValueError("Unreadable MSBT file")
        with file.open("rb") as opened:
            opened.seek(8)
            self._be = opened.read(2) == b"\xFE\xFF"

    def to_yaml(self) -> str:
        return self._msyt

    def to_msbt(self, output: Path):
        with NamedTemporaryFile(
            mode="w", suffix=".msyt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(self._msyt)
            tmp_name = tmp.name
        pymsyt.create(tmp_name, output, platform="wiiu" if self._be else "switch")

    @property
    def big_endian(self) -> bool:
        return self._be

@lru_cache(1)
def _init_deepmerge_name_table():
    table = get_default_name_table()
    for i in range(10000):
        table.add_name(f"File_{i}")

def open_yaml(file: Path) -> dict:
    yaml: str
    big_endian: bool
    obj: Union[oead.byml.Hash, oead.byml.Array, oead.aamp.ParameterIO, Msbt]
    obj_type: str
    if file.suffix == ".msbt":
        obj = Msbt(file)
        big_endian = obj.big_endian
        yaml = obj.to_yaml()
        obj_type = "msbt"
    else:
        data = file.read_bytes()
        if data[0:4] == b"Yaz0":
            data = oead.yaz0.decompress(data)
        if data[0:4] == b"AAMP":
            obj = oead.aamp.ParameterIO.from_binary(data)
            big_endian = False
            _init_deepmerge_name_table()
            yaml = obj.to_text()
            obj_type = "aamp"
        elif data[0:2] in {b"BY", b"YB"}:
            obj = oead.byml.from_binary(data)
            big_endian = data[0:2] == b"BY"
            yaml = oead.byml.to_text(obj)
            obj_type = "byml"
        else:
            raise ValueError()
    return {"yaml": yaml, "big_endian": big_endian, "obj": obj, "type": obj_type}


def get_sarc_yaml(file) -> dict:
    yaml: str
    big_endian: bool
    obj: Union[oead.byml.Hash, oead.byml.Array, oead.aamp.ParameterIO, Msbt]
    obj_type: str
    if file.name.endswith(".msbt"):
        with NamedTemporaryFile(suffix=".msbt", delete=False) as tmp:
            tmp_file = Path(tmp.name)
        tmp_file.write_bytes(file.data)
        obj = Msbt(tmp_file)
        big_endian = obj.big_endian
        yaml = obj.to_yaml()
        obj_type = "msbt"
    else:
        data = file.data if file.data[0:4] != b"Yaz0" else oead.yaz0.decompress(file.data)
        if data[0:4] == b"AAMP":
            obj = oead.aamp.ParameterIO.from_binary(data)
            big_endian = False
            yaml = obj.to_text()
            obj_type = "aamp"
        elif data[0:2] in {b"BY", b"YB"}:
            obj = oead.byml.from_binary(data)
            big_endian = data[0:2] == b"BY"
            yaml = oead.byml.to_text(obj)
            obj_type = "byml"
        else:
            raise ValueError()
    return {"yaml": yaml, "big_endian": big_endian, "obj": obj, "type": obj_type}


def save_yaml(yaml: str, obj_type: str, big_endian: bool = False):
    if obj_type == "aamp":
        return oead.aamp.ParameterIO.from_text(yaml).to_binary()
    elif obj_type == "byml":
        return oead.byml.to_binary(oead.byml.from_text(yaml), big_endian=big_endian)
    elif obj_type == "msbt":
        with NamedTemporaryFile(
            mode="w", suffix=".msyt", encoding="utf-8", delete=False
        ) as tmp:
            Path(tmp.name).write_text(yaml, encoding="utf-8")
            tmp_file = Path(tmp.name).with_suffix(".msbt")
        pymsyt.create(tmp.name, tmp_file, platform="wiiu" if big_endian else "switch")
        return tmp_file.read_bytes()
