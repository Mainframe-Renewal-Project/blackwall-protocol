
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Label, LoadingIndicator

from blackwall.api import user
from blackwall.api import resource
from blackwall.messages import OpenTab
from blackwall.panels.resource.generator import get_resource_objects_for_panel
from blackwall.panels.search.search_backend import QueryType
from blackwall.panels.users.generator import get_user_objects_for_panel

USER_COLUMNS = [
    ("User", "Name", "Owner", "Group","Last logon", "Created", "UID", "Shell", "Home"),
]

GROUP_COLUMNS = [
    ("Group", "Connected users", "Created"),
]

DATASET_COLUMNS = [
    ("Dataset", "UACC", "Owner", "Created"),
]

class PanelResultsUsers(Vertical):
    def __init__(self, user_dict: dict):
        super().__init__()
        self.user_dict = user_dict

    def compose(self) -> ComposeResult:
        yield Label("Users:")
        yield LoadingIndicator(id="results_user_loading")
        yield DataTable(id="results_user_table")

    def on_mount(self) -> None:
        user_table = self.get_child_by_id("results_user_table",DataTable)
        user_table.zebra_stripes = True
        user_table.add_columns(*USER_COLUMNS[0])
        self._load_user_rows()

    @work(thread=True, exclusive=True)
    def _load_user_rows(self) -> None:
        rows = []
        try:
            if "profiles" in self.user_dict:
                for user_entry in self.user_dict["profiles"]:
                    user_info = user.get_user(username=user_entry)
                    if "profile" in user_info:
                        base_traits = user.BaseUserTraits.from_dict(prefix="base",source=user_info["profile"]["base"])

                        uid_temp = ""
                        shell_temp = ""
                        home_temp = ""

                        if 'omvs' in user_info['profile']:
                            omvs_traits = user.OMVSUserTraits.from_dict(prefix="omvs",source=user_info["profile"]["omvs"])

                            uid_temp = omvs_traits.uid
                            shell_temp = omvs_traits.default_shell
                            home_temp = omvs_traits.home_directory
                        
                        if base_traits.last_access_date is not None and base_traits.last_access_time is not None:
                            logon_date = f"{base_traits.last_access_date} at {base_traits.last_access_time}"
                        else:
                            logon_date = ""
                        
                        rows.append((
                            user_entry,
                            base_traits.name,
                            base_traits.owner,
                            base_traits.default_group,
                            logon_date,
                            base_traits.create_date,
                            uid_temp,
                            shell_temp,
                            home_temp,
                        ))
                    else:
                        rows.append((user_entry, "", "", "", "", "", "", "", ""))
        except Exception as error:
            self.app.call_from_thread(self._show_user_error, error)
            return

        self.app.call_from_thread(self._show_user_rows, rows)

    def _show_user_rows(self, rows: list[tuple]) -> None:
        if not self.is_mounted:
            return
        self.get_child_by_id("results_user_loading",LoadingIndicator).remove()
        if rows:
            self.get_child_by_id("results_user_table",DataTable).add_rows(rows)

    def _show_user_error(self, error: Exception) -> None:
        if not self.is_mounted:
            return
        self.get_child_by_id("results_user_loading",LoadingIndicator).remove()
        self.notify(f"Could not load user results: {error}",severity="error")

    def key_enter(self) -> None:
        datatable = self.query_exactly_one("#results_user_table", DataTable)
        column_index = datatable.cursor_column
        if column_index == 0:
            current_row = datatable.cursor_coordinate
            cell_info = datatable.get_cell_at(current_row)
            new_user_panel = get_user_objects_for_panel(cell_info)

            self.post_message(OpenTab(f"User: {cell_info}",new_user_panel))

class PanelResultsGroup(Vertical):
    def __init__(self, group_dict: dict):
        super().__init__()
        self.group_dict = group_dict

    def compose(self) -> ComposeResult:
        yield Label("Groups:")
        yield DataTable(id="results_group_table")    

    def on_mount(self) -> None:
        group_table = self.get_child_by_id("results_group_table",DataTable)
        group_table.zebra_stripes = True
        group_table.add_columns(*GROUP_COLUMNS[0])

class PanelResultsDatasets(Vertical):
    def __init__(self, dataset_dict: dict):
        super().__init__()
        self.dataset_dict = dataset_dict

    def compose(self) -> ComposeResult:
        yield Label("Dataset profiles:")
        yield DataTable(id="results_dataset_table")        

    def on_mount(self) -> None:
        dataset_table = self.get_child_by_id("results_dataset_table",DataTable)
        dataset_table.zebra_stripes = True
        dataset_table.add_columns(*DATASET_COLUMNS[0])

class PanelResultsResources(Vertical):
    def __init__(self, resource_dict: dict, resource_class: str | None = None):
        super().__init__()
        self.resource_dict = resource_dict
        self.resource_class = resource_class

    def compose(self) -> ComposeResult:
        yield Label(f"Resource profiles ({self.resource_class or 'all classes'}):")
        yield DataTable(id="results_resource_table")

    def on_mount(self) -> None:
        resource_table = self.get_child_by_id("results_resource_table",DataTable)
        resource_table.zebra_stripes = True
        resource_table.add_column("Resource")
        profiles = self.resource_dict.get("profiles", [])
        if profiles:
            resource_table.add_rows((profile,) for profile in profiles)

    def key_enter(self) -> None:
        if self.resource_class is None:
            return
        resource_table = self.query_exactly_one("#results_resource_table",DataTable)
        if resource_table.row_count == 0 or resource_table.cursor_column != 0:
            return
        resource_name = resource_table.get_cell_at(resource_table.cursor_coordinate)
        resource_dict = resource.get_resource_profile(
            resource_class=self.resource_class,
            resource=resource_name,
        )
        if resource_dict and resource_dict["return_codes"]["racf_return_code"] == 0:
            panel = get_resource_objects_for_panel(
                resource_name=resource_name,
                resource_class=self.resource_class,
                resource_dict=resource_dict,
            )
            self.post_message(OpenTab(f"Resource: {resource_name}", panel))

class PanelResultsMixedType(Vertical):
    def __init__(self, results: dict[QueryType,dict]):
        super().__init__()
        self.results = results

    def compose(self) -> ComposeResult:
        if QueryType.User in self.results:
            yield PanelResultsUsers(user_dict=self.results[QueryType.User])
        if QueryType.Group in self.results:
            yield PanelResultsGroup(group_dict=self.results[QueryType.Group])
        if QueryType.Dataset in self.results:
            yield PanelResultsDatasets(dataset_dict=self.results[QueryType.Dataset])
        if QueryType.Resource in self.results:
            yield PanelResultsResources(resource_dict=self.results[QueryType.Resource])