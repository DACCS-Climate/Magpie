from magpie import *
from owsrequest import *
from models import find_children_by_name
from pyramid.security import Everyone as EVERYONE


class ServiceI(object):
    permission_names = []
    params_expected = []    # derived services must have 'request' at least for 'permission_requested' method
    resource_types = []

    def __init__(self, service, request):
        self.service = service
        self.request = request
        self.acl = []
        self.parser = ows_parser_factory(request)
        self.parser.parse(self.params_expected)

    @property
    def __acl__(self):
        raise NotImplementedError

    def expand_acl(self, resource, user):
        if resource:
            for ace in resource.__acl__:
                self.acl.append(ace)
            # Custom acl

            if user:
                permissions = resource.perms_for_user(user)
                for outcome, perm_user, perm_name in permission_to_pyramid_acls(permissions):
                    self.acl.append((outcome, perm_user, perm_name,))
            else:
                user = UserService.by_user_name(ANONYMOUS_USER, db_session=self.request.db)
                if user is None:
                    raise Exception('No Anonymous user in the database')
                else:
                    permissions = resource.perms_for_user(user)
                    for outcome, perm_user, perm_name in permission_to_pyramid_acls(permissions):
                        self.acl.append((outcome, EVERYONE, perm_name,))

    def permission_requested(self):
        try:
            return self.parser.params[u'request']
        except Exception as e:
            # if 'ServiceI', 'params_expected' is empty and will raise a KeyError
            raise NotImplementedError("Exception: [" + repr(e) + "]")


class ServiceWPS(ServiceI):

    permission_names = [u'getcapabilities',
                        u'describeprocess',
                        u'execute']

    params_expected = [u'service',
                       u'request',
                       u'version']

    def __init__(self, service, request):
        super(ServiceWPS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        return self.acl


class ServiceWMS(ServiceI):

    permission_names = [u'getcapabilities',
                        u'getmap',
                        u'getfeatureinfo',
                        u'getlegendgraphic',
                        u'getmetadata']

    params_expected = [u'service',
                       u'request',
                       u'version',
                       u'layers']

    resource_types = [models.Workspace.resource_type_name]

    def __init__(self, service, request):
        super(ServiceWMS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)

        #localhost:8087/geoserver/WATERSHED/wms?layers=WATERSHED:BV_1NS&request=getmap
        #localhost:8087/geoserver/wms?layers=WATERERSHED:BV1_NS&request=getmap
        #those two request lead to the same thing so, here we need to check the workspace in the layer

        #localhost:8087/geoserver/wms?request=getcapabilities (dangerous, get all workspace)
        # localhost:8087/geoserver/WATERSHED/wms?request=getcapabilities (only for the workspace in the path)
        #here we need to check the workspace in the path

        request_type = self.permission_requested()
        if request_type == 'getcapabilities':
            path_elem = self.request.path.split('/')
            wms_idx = path_elem.index('wms')
            if path_elem[wms_idx-1] != 'geoserver':
                workspace_name = path_elem[wms_idx-1]
            else:
                workspace_name = ''
        else:
            layer_name = self.parser.params['layers']
            workspace_name = layer_name.split(':')[0]

        # load workspace resource from the database
        workspace = find_children_by_name(name=workspace_name,
                                          parent_id=self.service.resource_id,
                                          db_session=self.request.db)
        if workspace:
            self.expand_acl(workspace, self.request.user)
        return self.acl


class ServiceWFS(ServiceI):

    permission_names = [u'getcapabilities',
                        u'describefeaturetype',
                        u'getfeature',
                        u'lockfeature',
                        u'transaction']

    params_expected = [u'service',
                       u'request',
                       u'version',
                       u'typenames']

    resource_types = []

    def __init__(self, service, request):
        super(ServiceWFS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        request_type = self.permission_requested()
        if request_type == 'getcapabilities':
            path_elem = self.request.path.split('/')
            wms_idx = path_elem.index('wfs')
            if path_elem[wms_idx - 1] != 'geoserver':
                workspace_name = path_elem[wms_idx - 1]
            else:
                workspace_name = ''
        else:
            layer_name = self.parser.params['typenames']
            workspace_name = layer_name.split(':')[0]

        # load workspace resource from the database
        workspace = find_children_by_name(name=workspace_name,
                                          parent_id=self.service.resource_id,
                                          db_session=self.request.db)
        if workspace:
            self.expand_acl(workspace, self.request.user)
        return self.acl


class ServiceTHREDDS(ServiceI):

    permission_names = models.File.permission_names

    params_expected = [u'request']

    resource_types = [models.Directory.resource_type_name,
                      models.File.resource_type_name]

    def __init__(self, service, request):
        super(ServiceTHREDDS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        elems = self.request.path.split('/')

        if 'fileServer' in elems:
            first_idx = elems.index('fileServer')
        elif 'dodsC' in elems:
            first_idx = elems.index('dodsC')
            elems[-1] = elems[-1].replace('.html', '')
        elif 'catalog' in elems:
            first_idx = elems.index('catalog')
        else:
            return self.acl

        elems = elems[first_idx+1::]
        db = self.request.db
        new_child = self.service
        while new_child and elems:
            name = elems.pop(0)
            new_child = find_children_by_name(name, parent_id=new_child.resource_id, db_session=db)
            self.expand_acl(new_child, self.request.user)

        return self.acl

    def permission_requested(self):
        return u'read'

    pass


service_type_dict = {u'wps': ServiceWPS,
                     u'wms': ServiceWMS,
                     u'wfs': ServiceWFS,
                     u'thredds': ServiceTHREDDS}


def service_factory(service, request):
    try:
        service_specific = service_type_dict[service.type](service, request)
        return service_specific
    except Exception as e:
        raise Exception("Failed to find requested service type. Exception: [" + repr(e) + "]")


def get_all_service_permission_names():
    all_permission_names_list = set()
    for service_type in service_type_dict.keys():
        all_permission_names_list.update(service_type_dict[service_type].permission_names)
    return all_permission_names_list
