from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Label

from blackwall.backout_journal import get_change_records, undo_change
from blackwall.modals import generic_confirmation_modal


class PanelBackout(VerticalScroll):
    def __init__(self) -> None:
        super().__init__()
        self._record_ids: list[str] = []
        self._records_by_id: dict[str, dict] = {}
        self._selected_record_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(
            "Tracks profile create, update, and delete actions made in Blackwall. "
            "Commands, permits, system options, and credentials are not backed out here.",
            classes="backout-label",
        )
        yield DataTable(id="backout_table")
        yield Button("Back out selected change", id="backout_button", action="backout", disabled=True)
        yield Button("Refresh history", id="backout_refresh_button", action="refresh_history")

    def on_mount(self) -> None:
        table = self.query_one("#backout_table", DataTable)
        table.zebra_stripes = True
        table.cursor_type = "row"
        self._refresh_records()

    def _refresh_records(self) -> None:
        table = self.query_one("#backout_table", DataTable)
        table.clear(columns=True)
        table.add_columns(("When", "timestamp"), ("Change", "description"), ("Backout", "status"))

        records = get_change_records()
        self._records_by_id = {record["id"]: record for record in records}
        self._record_ids = []
        rows = []
        for record in records:
            self._record_ids.append(record["id"])
            undo_warning = record.get("undo_warning")
            if record["status"] == "backed_out":
                status = "Backed out"
            elif record["status"] == "available" and undo_warning:
                status = f"Partial: {undo_warning}"
            elif record["status"] == "available":
                status = "Ready"
            else:
                status = f"Unavailable: {undo_warning or 'no safe inverse'}"
            rows.append((record["timestamp"], record["description"], status))

        if rows:
            table.add_rows(rows)
            table.move_cursor(row=0)
            self._select_record(0)
        else:
            self._selected_record_id = None
            self.query_one("#backout_button", Button).disabled = True

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._select_record(event.cursor_row)

    def _select_record(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._record_ids):
            self._selected_record_id = None
            self.query_one("#backout_button", Button).disabled = True
            return

        record_id = self._record_ids[row_index]
        record = self._records_by_id[record_id]
        self._selected_record_id = record_id
        self.query_one("#backout_button", Button).disabled = (
            record["status"] != "available" or record.get("undo_request") is None
        )

    def action_refresh_history(self) -> None:
        self._refresh_records()

    def action_backout(self) -> None:
        if self._selected_record_id is None:
            self.notify("Select a change first", severity="warning")
            return

        record = self._records_by_id[self._selected_record_id]
        if record["status"] != "available" or record.get("undo_request") is None:
            self.notify(record.get("undo_warning") or "This change is not available for backout", severity="warning")
            return

        warning = record.get("undo_warning")
        confirmation = f"Back out this change?\n{record['description']}"
        if warning:
            confirmation += f"\n\nNote: {warning}"
        generic_confirmation_modal(
            self,
            modal_text=confirmation,
            confirm_action="execute_backout",
            action_widget=self,
        )

    def action_execute_backout(self) -> None:
        record_id = self._selected_record_id
        if record_id is None:
            return
        self.query_one("#backout_button", Button).disabled = True
        self._run_backout(record_id)

    @work(thread=True, exclusive=True)
    def _run_backout(self, record_id: str) -> None:
        try:
            return_code, message = undo_change(record_id)
        except Exception as error:
            self.app.call_from_thread(self._backout_failed, str(error))
            return
        self.app.call_from_thread(self._backout_finished, record_id, return_code, message)

    def _backout_finished(self, record_id: str, return_code: int, message: str) -> None:
        if not self.is_mounted:
            return
        self._refresh_records()
        record = self._records_by_id.get(record_id)
        description = record["description"] if record is not None else "change"
        if return_code in {0, 4}:
            self.notify(f"Backed out: {description}", severity="information")
        else:
            self.notify(f"Could not back out change: {message}", severity="error")

    def _backout_failed(self, error: str) -> None:
        if not self.is_mounted:
            return
        self._refresh_records()
        self.notify(f"Could not back out change: {error}", severity="error")