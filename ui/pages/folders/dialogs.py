from PySide6.QtWidgets import QHBoxLayout

from ui.pages.playlists.dialogs import ThemedDialog
from ui.shell.header import CapsuleButton


def notice(parent, title: str, message: str):
    """A message in the app's own dialog look, with a single OK."""
    d = ThemedDialog(parent, title, message)
    d.body.addSpacing(4)
    row = QHBoxLayout()
    row.addStretch(1)
    ok = CapsuleButton("OK", "primary")
    ok.clicked.connect(d.accept)
    row.addWidget(ok)
    d.body.addLayout(row)
    d.exec()