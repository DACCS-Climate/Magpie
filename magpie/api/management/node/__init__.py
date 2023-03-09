from magpie.api import schemas as s
from magpie.utils import get_logger

LOGGER = get_logger(__name__)

def includeme(config):
    LOGGER.info("Adding API node...")
    config.add_route(**s.service_api_route_info(s.NodeAdminAPI))

    