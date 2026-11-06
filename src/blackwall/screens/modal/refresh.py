
from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import Screen
from textual.widgets import Button, Input, Label

from blackwall.api.setropts import refresh_racf


class RefreshScreen(Screen):
    """Refresh RACF database screen"""

    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Refresh in-storage generic profiles for this RACF class?", id="question"),
            Input(id="class_name",placeholder="RACF class (e.g. DATASET)",max_length=8,classes="refresh-class-input"),
            Button("Cancel", variant="primary", id="cancel", classes="modal-buttons"),
            Button("Confirm", variant="error", id="confirm", classes="modal-buttons"),
            id="dialog",
            classes="refresh-dialog",
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            class_name = self.query_one("#class_name",Input).value.strip().upper()
            if not class_name:
                self.notify("Enter a RACF class to refresh",severity="warning")
                return

            return_code = refresh_racf(class_name)
            if return_code == 0:
                self.notify(f"Refresh for class {class_name} successfully issued, return code: {return_code}",severity="information")
            else:
                self.notify(f"Refresh for class {class_name} failed, return code: {return_code}",severity="error")
            self.app.pop_screen()
        else:
            self.app.pop_screen()
