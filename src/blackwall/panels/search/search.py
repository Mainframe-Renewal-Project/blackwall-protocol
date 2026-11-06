
#TODO fix all of this shitty code. Not gonna lie the code below is really bad, but I was in a crunch

from textual import on
from textual.app import ComposeResult
from textual.containers import HorizontalGroup, VerticalGroup, VerticalScroll
from textual.suggester import SuggestFromList
from textual.widgets import Button, ContentSwitcher, Input, Label

from blackwall.api import dataset, group, keyrings, resource, user
from blackwall.api.setropts import get_active_classes
from blackwall.emoji import get_emoji
from blackwall.messages import OpenTab
from blackwall.panels.dataset.dataset import DatasetInfo, PanelDataset
from blackwall.panels.group.group import GroupInfo, PanelGroup
from blackwall.panels.keyrings.keyrings import KeyringInfo, PanelKeyring
from blackwall.panels.resource.generator import get_resource_objects_for_panel
from blackwall.panels.search.results import (
    PanelResultsDatasets,
    PanelResultsGroup,
    PanelResultsMixedType,
    PanelResultsResources,
    PanelResultsUsers,
)
from blackwall.panels.search.search_backend import QueryType, search_database_query_one
from blackwall.panels.users.generator import get_user_objects_for_panel
from blackwall.regex import racf_id_regex


class PanelSearchUser(VerticalGroup):
    def __init__(self, search_action: str, id: str):  # noqa: A002
        super().__init__()
        self.id = id
        self.search_action = search_action

    def compose(self) -> ComposeResult:
        yield Label("Search users",classes="search-label")
        yield Input(max_length=8,placeholder="id...",restrict=racf_id_regex,id="search_field",classes="field-short-generic")
        yield Button(label=f"{get_emoji("🔎")} Search",action="search")

    async def action_search(self):
        await self.app.run_action(self.search_action,default_namespace=self.parent.parent)

class PanelSearchGroup(VerticalGroup):
    def __init__(self, search_action: str, id: str):  # noqa: A002
        super().__init__()
        self.id = id
        self.search_action = search_action

    def compose(self) -> ComposeResult:
        yield Label("Search for group",classes="search-label")
        yield Input(max_length=8,placeholder="id...",id="search_field",restrict=racf_id_regex,classes="field-short-generic")
        yield Button(label=f"{get_emoji("🔎")} Search",action="search")

    async def action_search(self):
        await self.app.run_action(self.search_action,default_namespace=self.parent.parent)

class PanelSearchDataset(VerticalGroup):
    def __init__(self, search_action: str, id: str):  # noqa: A002
        super().__init__()
        self.id = id
        self.search_action = search_action

    def compose(self) -> ComposeResult:
        yield Label("Search for dataset profile",classes="search-label")
        yield Input(max_length=255,placeholder="dataset profile name...",id="search_field",classes="field-long-generic")
        yield Button(label=f"{get_emoji("🔎")} Search",action="search")

    async def action_search(self):
        await self.app.run_action(self.search_action,default_namespace=self.parent.parent)

class PanelSearchResource(VerticalGroup):
    def __init__(self, search_action: str, id: str):  # noqa: A002
        super().__init__()
        self.id = id
        self.search_action = search_action

    active_classes = get_active_classes()

    def compose(self) -> ComposeResult:
        yield Label("Search for resource profile",classes="search-label")
        yield Input(max_length=8,id="search_field_class",suggester=SuggestFromList(self.active_classes,case_sensitive=False),placeholder="class...",classes="field-short-generic")
        yield Input(max_length=255,id="search_field",placeholder="resource profile...",classes="field-long-generic")
        yield Button(label=f"{get_emoji("🔎")} Search",action="search")

    async def action_search(self):
        await self.app.run_action(self.search_action,default_namespace=self.parent.parent)

class PanelSearchSwitcherButtons(HorizontalGroup):
    def compose(self) -> ComposeResult:
        yield Button(id="search_user_panel_button",label="User",classes="search-buttons",name="search_user_panel")
        yield Button(id="search_group_panel_button",label="Group",classes="search-buttons",name="search_group_panel")
        yield Button(id="search_dataset_panel_button",label="Dataset profile",classes="search-buttons",name="search_dataset_panel")
        yield Button(id="search_resource_panel_button",label="Resource profile",classes="search-buttons",name="search_resource_panel")
        #yield Button(id="search_keyring_panel",label="Keyring",classes="search-buttons")

class PanelSearch(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield PanelSearchSwitcherButtons()
        with ContentSwitcher(initial="search_user_panel",id="search_switcher",classes="search-switcher"):
            yield PanelSearchUser(search_action="search",id="search_user_panel")
            yield PanelSearchGroup(search_action="search",id="search_group_panel")
            yield PanelSearchDataset(search_action="search",id="search_dataset_panel")
            yield PanelSearchResource(search_action="search",id="search_resource_panel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.query_one(ContentSwitcher).current = event.button.name  

    @on(Input.Submitted)
    def action_search(self) -> None:
        search_switcher_id = self.query_exactly_one("#search_switcher", ContentSwitcher).current
        if search_switcher_id is not None:
            search_query = self.query_exactly_one(f"#{search_switcher_id}").query_exactly_one("#search_field",Input).value
        
            if search_switcher_id == "search_any_panel":
                results = search_database_query_one(query=search_query, class_name=None,query_types=QueryType.all())
                self.post_message(OpenTab("Results",PanelResultsMixedType(results)))
            elif search_switcher_id == "search_user_panel":
                user_dict = user.get_user(search_query)
                if user_dict and user_dict["return_codes"]["racf_return_code"] == 0:
                    new_user_panel = get_user_objects_for_panel(search_query, user_dict)
                    
                    self.post_message(OpenTab(f"User: {search_query}",new_user_panel))

                    self.notify(f"Found user: {search_query}")
                else:
                    if search_query == "" or search_query == "*":
                        search_results = user.get_users()
                    else:
                        search_results = user.search_users(query=search_query)
                    results_panel = PanelResultsUsers(search_results)
                    self.post_message(OpenTab("Results",results_panel))
            elif search_switcher_id == "search_group_panel":
                group_dict = group.get_group(group=search_query)
                if group_dict and group_dict["return_codes"]["racf_return_code"] == 0:
                    new_group_panel = PanelGroup()
                
                    base_traits = group.BaseGroupTraits.from_dict(prefix="base",source=group_dict["profile"]["base"])

                    new_group_panel.group_info = GroupInfo(
                        base_traits=base_traits,
                        group_name=search_query,
                    )

                    if 'profile' in group_dict and 'dfp' in group_dict['profile']:
                        new_group_panel.group_info.dfp_traits = group.DFPGroupTraits.from_dict(prefix="dfp",source=group_dict["profile"]["dfp"])

                    self.post_message(OpenTab(f"Group: {search_query}",new_group_panel))

                    self.notify(f"Found group: {search_query}")
                else:
                    if search_query in ("", "*"):
                        group_results = group.get_groups()
                    else:
                        group_results = group.search_group(search_query)
                    self.post_message(OpenTab("Groups",PanelResultsGroup(group_results)))
            elif search_switcher_id == "search_dataset_panel":
                dataset_dict = dataset.get_dataset_profile(dataset=search_query)
                if dataset_dict and dataset_dict["return_codes"]["racf_return_code"] == 0:
                    new_dataset_panel = PanelDataset()
                
                    base_traits = dataset.BaseDatasetTraits.from_dict(prefix="base",source=dataset_dict["profile"]["base"])

                    new_dataset_panel.dataset_info = DatasetInfo(
                        base_traits=base_traits,
                        profile_name=search_query,
                    )

                    self.post_message(OpenTab(f"Dataset: {search_query}",new_dataset_panel))

                    self.notify(f"Found dataset profile: {search_query}")
                else:
                    if search_query in ("", "*"):
                        dataset_results = dataset.get_dataset_profiles()
                    else:
                        dataset_results = dataset.search_dataset_profiles(search_query)
                    self.post_message(OpenTab("Dataset profiles",PanelResultsDatasets(dataset_results)))
            elif search_switcher_id == "search_resource_panel":
                search_query_class = self.query_exactly_one(f"#{search_switcher_id}").query_exactly_one("#search_field_class",Input).value
                if not search_query_class:
                    self.notify("Enter a resource class to search",severity="warning")
                    return

                resource_dict = resource.get_resource_profile(
                    resource_class=search_query_class,
                    resource=search_query,
                )
                if resource_dict and resource_dict["return_codes"]["racf_return_code"] == 0:
                    panel = get_resource_objects_for_panel(
                        resource_name=search_query,
                        resource_class=search_query_class,
                        resource_dict=resource_dict,
                    )
                    self.post_message(OpenTab(f"Resource: {search_query}",panel))
                    self.notify(f"Found resource profile: {search_query}")
                else:
                    if search_query in ("", "*"):
                        resource_results = resource.get_resource_profiles(search_query_class)
                    else:
                        resource_results = resource.search_resource_profiles(
                            resource_class=search_query_class,
                            query=search_query,
                        )
                    self.post_message(OpenTab(
                        f"Resource profiles: {search_query_class}",
                        PanelResultsResources(resource_results, search_query_class),
                    ))
            elif search_switcher_id == "search_keyring_panel":
                search_query_keyring_owner = self.query_exactly_one(f"#{search_switcher_id}").query_exactly_one("#search_field_keyring_owner",Input).value

                if keyrings.keyring_exists(keyring=search_query,owner=search_query_keyring_owner):
                    new_keyring_panel = PanelKeyring()

                    key_dict = keyrings.get_keyring(keyring=search_query,owner=search_query_keyring_owner)

                    keyring_traits = keyrings.KeyringTraits.from_dict(prefix=None,source=key_dict)

                    new_keyring_panel.keyring_info = KeyringInfo(
                        keyring_name=search_query,
                        keyring_owner=search_query_keyring_owner,
                        keyring_traits=keyring_traits,
                    )

                    self.post_message(OpenTab(f"Keyring: {search_query}",new_keyring_panel))

                    self.notify(f"Found keyring: {search_query}")
                else:
                    self.notify(f"Keyring {search_query} couldn't be found")
