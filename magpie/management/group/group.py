from magpie import *
import models
from models import resource_type_dico
from models import resource_tree_service
from management.service.service import format_service, format_resource
from management.service.resource import format_resource_tree, get_resource_children, crop_tree_with_permission


@view_config(route_name='groups', request_method='GET')
def get_groups(request):
    group_name_list = [group.group_name for group in models.Group.all(db_session=request.db)]
    json_response = {'group_names': group_name_list}
    return HTTPOk(
        body=json.dumps(json_response),
        content_type='application/json'
    )


@view_config(route_name='groups', request_method='POST')
def create_group(request):
    try:
        db = request.db
        group_name = request.POST.get('group_name')
        new_group = models.Group(group_name=group_name)
        db.add(new_group)
        db.commit()
    except:
        # Group already exist
        db.rollback()
        raise HTTPConflict(detail='This name already exists')

    return HTTPCreated()


@view_config(route_name='group', request_method='DELETE')
def delete_group(request):
    group_name = request.matchdict.get('group_name')
    try:
        db = request.db
        group = GroupService.by_group_name(group_name, db_session=db)
        db.delete(group)
        db.commit()

    except:
        db.rollback()
        raise HTTPNotFound(detail="This group does not exist")

    return HTTPOk()


@view_config(route_name='group_users', request_method='GET')
def get_group_users(request):
    group_name = request.matchdict.get('group_name')
    try:
        db = request.db
        group = GroupService.by_group_name(group_name, db_session=db)
        json_response = {'user_names': [user.user_name for user in group.users]}
    except:
        raise HTTPNotFound(detail="This group does not exist")

    return HTTPOk(
        body=json.dumps(json_response),
        content_type='application/json'
    )


def get_group_services_permissions(group, db_session, resource_ids=None):
    resources_permissions = get_group_resources_permissions_dict(group, resource_types=['service'], db_session=db_session, resource_ids=resource_ids)
    group_services_permissions = []
    for resource_id, resource_perm in resources_permissions.items():
        curr_service = models.Service.by_resource_id(resource_id, db_session=db_session)
        group_services_permissions.append((curr_service, resource_perm))
    return group_services_permissions


@view_config(route_name='group_services', request_method='GET')
def get_group_services_view(request):
    group = GroupService.by_group_name(request.matchdict.get('group_name'), db_session=request.db)

    json_response = {}
    resources_permissions_dict = get_group_resources_permissions_dict(group,
                                                                      resource_types=['service'],
                                                                      db_session=request.db)

    for resource_id, perms in resources_permissions_dict.items():
        curr_service = models.Service.by_resource_id(resource_id=resource_id, db_session=request.db)
        service_type = curr_service.type
        service_name = curr_service.resource_name
        if service_type not in json_response:
            json_response[service_type] = {}
        json_response[service_type][service_name] = format_service(curr_service, perms)

    return HTTPOk(
        body=json.dumps({'services': json_response}),
        content_type='application/json'
    )


from services import service_type_dico
@view_config(route_name='group_service_permissions', request_method='GET')
def get_group_service_permissions_view(request):
    group_name = request.matchdict.get('group_name')
    service_name = request.matchdict.get('service_name')

    db = request.db
    service = models.Service.by_service_name(service_name, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if service is None or group is None:
        raise HTTPNotFound(detail='this service/group does not exist')

    if service.owner_group_id == group.id:
        permission_names = service_type_dico[service.type].permission_names
    else:
        service_found_perms_list = get_group_services_permissions(group, db_session=db, resource_ids=[service.resource_id])
    if service_found_perms_list:
        service_found, perms = service_found_perms_list[0]

    json_response = {service.resource_name: format_service(service)}
    json_response[service.resource_name]['permission_names'] = perms
    return HTTPOk(
        body=json.dumps(json_response),
        content_type='application/json'
    )


@view_config(route_name='group_service_permissions', request_method='POST')
def create_group_service_permission(request):
    group_name = request.matchdict.get('group_name')
    service_name = request.matchdict.get('service_name')
    permission_name = request.POST.get('permission_name')

    db = request.db
    service = models.Service.by_service_name(service_name, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if service is None or group is None:
        db.rollback()
        raise HTTPNotFound(detail='this service/group does not exist')
    if permission_name not in service_type_dico[service.type].permission_names:
        db.rollback()
        raise HTTPBadRequest(detail='This permission is not allowed for that service')

    return create_group_resource_permission(permission_name, service.resource_id, group.id, db_session=db)

@view_config(route_name='group_service_permission', request_method='DELETE')
def delete_group_service_permission(request):
    group_name = request.matchdict.get('group_name')
    service_name = request.matchdict.get('service_name')
    permission_name = request.matchdict.get('permission_name')

    db = request.db
    service = models.Service.by_service_name(service_name, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if service is None or group is None:
        raise HTTPNotFound(detail='this service/group does not exist')
    if permission_name not in service_type_dico[service.type].permission_names:
        raise HTTPBadRequest(detail='This permission is not allowed for that service')
    return delete_group_resource_permission(permission_name, service.resource_id, group.id, db_session=db)


def get_group_resources_permissions_dict(group, db_session, resource_ids=None, resource_types=None):
    db = db_session
    if group is None:
        raise HTTPBadRequest(detail='This group does not exist')
    resource_permission_tuple = group.resources_with_possible_perms(resource_ids=resource_ids, resource_types=resource_types, db_session=db)
    resources_permissions_dict = {}
    for tuple in resource_permission_tuple:
        if tuple.resource.resource_id not in resources_permissions_dict:
            resources_permissions_dict[tuple.resource.resource_id] = [tuple.perm_name]
        else:
            resources_permissions_dict[tuple.resource.resource_id].append(tuple.perm_name)

    return resources_permissions_dict


@view_config(route_name='group_resources', request_method='GET')
def get_group_resources_view(request):
    group = GroupService.by_group_name(request.matchdict.get('group_name'), db_session=request.db)
    resources = models.Resource.all(db_session=request.db)
    resource_info_dico = {}
    from management.service.resource import format_resource_with_children
    for resource in resources:
        resource_info_dico[resource.resource_id] = format_resource_with_children(resource,
                                                                                 db_session=request.db,
                                                                                 group=group)

    json_response = {'resources': resource_info_dico}
    return HTTPOk(
        body=json.dumps(json_response),
        content_type='application/json'
    )

@view_config(route_name='group_resources_type', request_method='GET')
def get_group_resources_type_view(request):
    group = GroupService.by_group_name(request.matchdict.get('group_name'), db_session=request.db)
    resource_type = request.matchdict.get('resource_type')
    resources_permissions_dict = get_group_resources_permissions_dict(group,
                                                                      resource_types=[resource_type],
                                                                      db_session=request.db)
    json_response = {}
    for resource_id, perms in resources_permissions_dict.items():
        resource = ResourceService.by_resource_id(resource_id, db_session=request.db)
        json_response[resource.resource_name] = format_resource(resource, perms)


    return HTTPOk(
        body=json.dumps({'resources': json_response}),
        content_type='application/json'
    )


def get_group_resource_permissions(group, resource, db_session):
    if resource.owner_group_id == group.id:
        permission_names = resource_type_dico[resource.type].permission_names
    else:
        group_res_permission = db_session.query(models.GroupResourcePermission) \
            .filter(models.GroupResourcePermission.resource_id == resource.resource_id) \
            .filter(models.GroupResourcePermission.group_id == group.id)
        permission_names = [permission.perm_name for permission in group_res_permission]
    return permission_names


def get_group_service_permissions(group, service, db_session):
    if service.owner_group_id == group.id:
        permission_names = service_type_dico[service.type].permission_names
    else:
        group_res_permission = db_session.query(models.GroupResourcePermission) \
            .filter(models.GroupResourcePermission.resource_id == service.resource_id) \
            .filter(models.GroupResourcePermission.group_id == group.id)
        permission_names = [permission.perm_name for permission in group_res_permission]
    return permission_names

@view_config(route_name='group_resource_permissions', request_method='GET')
def get_group_resource_permissions_view(request):
    group_name = request.matchdict.get('group_name')
    resource_id = request.matchdict.get('resource_id')

    db = request.db
    resource = ResourceService.by_resource_id(resource_id=resource_id, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if resource is None or group is None:
        raise HTTPNotFound(detail='this resource/group does not exist')

    permission_names = get_group_resource_permissions(group, resource, db_session=db)

    return HTTPOk(
        body=json.dumps({'permission_names': permission_names}),
        content_type='application/json'
    )


def create_group_resource_permission(permission_name, resource_id, group_id, db_session):
    try:
        new_permission = models.GroupResourcePermission(resource_id=resource_id, group_id=group_id)
        new_permission.perm_name = permission_name
        db_session.add(new_permission)
        db_session.commit()
    except:
        db_session.rollback()
        raise HTTPConflict('This permission on that service already exists for that group')
    return HTTPOk()

@view_config(route_name='group_resource_permissions', request_method='POST')
def create_group_resource_permission_view(request):
    group_name = request.matchdict.get('group_name')
    resource_id = request.matchdict.get('resource_id')
    permission_name = request.POST.get('permission_name')

    db = request.db
    resource = ResourceService.by_resource_id(resource_id, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if resource is None or group is None:
        raise HTTPNotFound(detail='this service/group does not exist')
    if permission_name not in resource_type_dico[resource.resource_type].permission_names:
        raise HTTPBadRequest(detail='This permission is not allowed for that service')

    return create_group_resource_permission(permission_name, resource.resource_id, group.id, db_session=db)



def delete_group_resource_permission(permission_name, resource_id, group_id, db_session):
    try:
        permission_to_delete = GroupResourcePermissionService.get(group_id, resource_id, permission_name, db_session=db_session)
        db_session.delete(permission_to_delete)
        db_session.commit()
    except:
        db_session.rollback()
        raise HTTPNotFound(detail="This permission on that service does not exist for that group")

    return HTTPOk()


@view_config(route_name='group_resource_permission', request_method='DELETE')
def delete_group_resource_permission_view(request):
    group_name = request.matchdict.get('group_name')
    resource_id = request.matchdict.get('resource_id')
    permission_name = request.matchdict.get('permission_name')

    db = request.db
    resource = ResourceService.by_resource_id(resource_id, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if resource is None or group is None:
        raise HTTPNotFound(detail='this service/group does not exist')
    if permission_name not in resource_type_dico[resource.resource_type].permission_names:
        raise HTTPBadRequest(detail='This permission is not allowed for that service')
    return delete_group_resource_permission(permission_name, resource.resource_id, group.id, db_session=db)



@view_config(route_name='group_service_resources', request_method='GET')
def get_group_service_resources_view(request):
    service_name = request.matchdict.get('service_name')
    group_name = request.matchdict.get('group_name')
    db = request.db
    service = models.Service.by_service_name(service_name, db_session=db)
    group = GroupService.by_group_name(group_name=group_name, db_session=db)
    if service is None or group is None:
        raise HTTPNotFound(detail='this service/group does not exist')

    resources_under_service = resource_tree_service.from_parent_deeper(parent_id=service.resource_id, db_session=db)
    tree_struct_dico = resource_tree_service.build_subtree_strut(resources_under_service)
    resources_permissions = get_group_resources_permissions_dict(group=group, db_session=db)

    json_response = {}
    tree_crop, resource_id_list_remain = crop_tree_with_permission(tree_struct_dico['children'],
                                                                   resources_permissions.keys())
    json_response[service_name] = format_service(service)
    json_response[service_name]['resources'] = format_resource_tree(tree_crop,
                                                                    db_session=db,
                                                                    group=group,
                                                                    user=None)
    return HTTPOk(
        body=json.dumps({'resources': json_response}),
        content_type='application/json'
    )





