from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.settings import asbool

from magpie.api import schemas as s
from magpie.api.management.register import register_views as rv
from magpie.constants import get_constant
from magpie.utils import get_logger

LOGGER = get_logger(__name__)


def includeme(config):
    LOGGER.info("Adding API register...")
    config.add_route(**s.service_api_route_info(s.RegisterGroupsAPI))
    config.add_route(**s.service_api_route_info(s.RegisterGroupAPI))
    config.add_route(**s.service_api_route_info(s.TemporaryUrlAPI))

    # Add route for receiving info about a node
    config.add_route(**s.service_api_route_info(s.RegisterNodeAPI))

    # Add route for receiving info about a node through a URL
    config.add_route(**s.service_api_route_info(s.RegisterNodeURLAPI))

    # Add route for receiving info about a node through a file such as JSON
    config.add_route(**s.service_api_route_info(s.RegisterNodeJSONAPI))

    register_user_enabled = asbool(get_constant("MAGPIE_USER_REGISTRATION_ENABLED", settings_container=config,
                                                default_value=False, print_missing=True,
                                                raise_missing=False, raise_not_set=False))
    if register_user_enabled:
        LOGGER.info("Adding user registration route.")
        config.add_route(**s.service_api_route_info(s.RegisterUsersAPI))
        config.add_route(**s.service_api_route_info(s.RegisterUserAPI))
        # only admins can view/list/remove pending users, but anyone can self-register with pending user approval
        config.add_view(rv.get_pending_users_view, route_name=s.RegisterUsersAPI.name, request_method="GET")
        config.add_view(rv.create_pending_user_view, route_name=s.RegisterUsersAPI.name, request_method="POST",
                        permission=NO_PERMISSION_REQUIRED)
        config.add_view(rv.get_pending_user_view, route_name=s.RegisterUserAPI.name, request_method="GET")
        config.add_view(rv.delete_pending_user_view, route_name=s.RegisterUserAPI.name, request_method="DELETE")
    else:
        LOGGER.info("User registration disabled [setting MAGPIE_USER_REGISTRATION].")

    config.scan()
