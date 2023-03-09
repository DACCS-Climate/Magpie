from magpie.api import schemas as s
from magpie.utils import get_logger

LOGGER = get_logger(__name__)

def includeme(config):
    LOGGER.info("Adding API node...")
    config.add_route(**s.service_api_route_info(s.NodeAdminAPI))

    # Add route for receiving info about a node
    config.add_route(**s.service_api_route_info(s.RegisterNodeAPI))

    # Add route for receiving info about a node through a URL
    config.add_route(**s.service_api_route_info(s.RegisterNodeURLAPI))

    # Add route for receiving info about a node through a file such as JSON
    config.add_route(**s.service_api_route_info(s.RegisterNodeJSONAPI))

