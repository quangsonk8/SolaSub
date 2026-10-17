"""Tim file icon — chay tu source lan tu ban dong goi deu phai ra dung cho."""
from PyQt6.QtGui import QIcon

from ..paths import resource

_NAMES = ("solasub.ico", "solasub.png")


def icon_path():
    for n in _NAMES:
        p = resource("assets", n)
        if p:
            return p
    return None


def app_icon():
    p = icon_path()
    return QIcon(p) if p else None
