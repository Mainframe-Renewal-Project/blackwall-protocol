from blackwall.api import resource as resource_api
from blackwall.api.traits_base import TraitsBase
from blackwall.panels.panel_mode import PanelMode
from blackwall.panels.resource.resource import PanelResource, ResourceInfo


def get_resource_objects_for_panel(
    resource_name: str,
    resource_class: str,
    resource_dict: dict | None = None,
) -> PanelResource:
    if resource_dict is None:
        resource_dict = resource_api.get_resource_profile(
            resource_class=resource_class,
            resource=resource_name,
        )

    profile = resource_dict["profile"]
    resource_info = ResourceInfo(
        base_traits=resource_api.BaseResourceTraits.from_dict(
            prefix="base",
            source=profile["base"],
        ),
        mode=PanelMode.edit,
        resource_name=resource_name,
        resource_class=resource_class,
    )

    trait_segments: tuple[tuple[str, str, type[TraitsBase]], ...] = (
        ("kerb", "kerb_traits", resource_api.KerbResourceTraits),
        ("dlf", "dlf_traits", resource_api.DLFDataResourceTraits),
        ("eim", "eim_traits", resource_api.EIMResourceTraits),
        ("jes", "jes_traits", resource_api.JESResourceTraits),
        ("icsf", "icsf_traits", resource_api.ICSFResourceTraits),
        ("ictx", "ictx_traits", resource_api.ICTXResourceTraits),
        ("idtparms", "idtparms_traits", resource_api.IDTPARMSResourceTraits),
        ("session", "session_traits", resource_api.SessionResourceTraits),
        ("svfmr", "svfmr_traits", resource_api.SVFMRResourceTraits),
        ("stdata", "stdata_traits", resource_api.STDATAResourceTraits),
        ("proxy", "proxy_traits", resource_api.ProxyResourceTraits),
        ("mfpolicy", "mfpolicy_traits", resource_api.MFPolicyResourceTraits),
        ("sigver", "sigver_traits", resource_api.SIGVERResourceTraits),
        ("tme", "tme_traits", resource_api.TMEResourceTraits),
        ("cdtinfo", "cdtinfo_traits", resource_api.CDTINFOResourceTraits),
        ("ssignon", "ssignon_traits", resource_api.SSIGNONResourceTraits),
        ("cfdef", "cfdef_traits", resource_api.CfdefResourceTraits),
    )
    for segment, attribute, trait_type in trait_segments:
        if segment in profile:
            setattr(
                resource_info,
                attribute,
                trait_type.from_dict(prefix=segment, source=profile[segment]),
            )

    panel = PanelResource()
    panel.resource_info = resource_info
    return panel