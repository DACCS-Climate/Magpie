from pyramid.view import view_config

from magpie.api import requests as ar
from magpie.api import exception as ax
from magpie.api.management.node import node_utils as nu
from magpie.api import schemas as s

#def node_manager_admin_view():

# Get node details through GET
@s.RegisterNodeAPI.get(schema=s.RegisterNode_GET_RequestSchema, tags=[s.NodeTag], response_schemas=s.RegisterNode_GET_responses)
@view_config(route_name=s.RegisterNodeAPI.name, request_method="GET")
def node_manager_register_view(request):
    """
    Registers a new node.
    """
    # accomplish basic validations here, create_service will do more field-specific checks
    node_name = ar.get_value_multiformat_body_checked(request, "node_name", pattern=ax.SCOPE_REGEX)
    node_url = ar.get_value_multiformat_body_checked(request, "node_url", pattern=ax.URL_REGEX)
    node_type = ar.get_value_multiformat_body_checked(request, "node_type")
    # service_push = asbool(ar.get_multiformat_body(request, "service_push", default=False))

    # Will need to implement different node configuration function
    node_cfg = ar.get_multiformat_body(request, "configuration")

    # Node creation not implemented
    return nu.create_node(node_name, node_type, node_url, node_cfg, db_session=request.db)



# Get node details through POST
@s.RegisterGroupAPI.post(schema=s.RegisterNode_POST_RequestSchema, tags=[s.NodeTag], response_schemas=s.RegisterNode_POST_responses)
@view_config(route_name=s.RegisterNodeAPI.name, request_method="POST")
def node_manager_register_view(request):
    """
    Registers a new node.
    """
    # accomplish basic validations here, create_service will do more field-specific checks
    node_name = ar.get_value_multiformat_body_checked(request, "node_name", pattern=ax.SCOPE_REGEX)
    node_url = ar.get_value_multiformat_body_checked(request, "node_url", pattern=ax.URL_REGEX)
    node_type = ar.get_value_multiformat_body_checked(request, "node_type")
    #service_push = asbool(ar.get_multiformat_body(request, "service_push", default=False))

    # Will need to implement different node configuration function
    node_cfg = ar.get_multiformat_body(request, "configuration")

    #Node creation not implemented
    return nu.create_node(node_name, node_type, node_url, node_cfg, db_session=request.db)
