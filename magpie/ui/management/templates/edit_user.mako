<%inherit file="ui.home:templates/template.mako"/>
<%inherit file="ui.management:templates/tree_scripts.mako"/>
<%namespace name="tree" file="ui.management:templates/tree_scripts.mako"/>

<%def name="render_item(key, value, level)">
    <input type="hidden" value="" name="edit_permissions">
    %for perm in permissions:
        % if perm in value['permission_names']:
            <div class="perm-checkbox">
                <label>
                <input type="checkbox" value="${perm}" name="permission"
                       onchange="document.getElementById('resource_${value['id']}_${value.get('remote_id', '')}').submit()"
                       checked
                    %if inherit_groups_permissions:
                        disabled
                    %endif
                >
                </label>
           </div>
        % else:
            <div class="perm-checkbox">
                <label>
                <input type="checkbox" value="${perm}" name="permission"
                       onchange="document.getElementById('resource_${value['id']}_${value.get('remote_id', '')}').submit()"
                    %if inherit_groups_permissions:
                        disabled
                    %endif
                >
                </label>
            </div>
        % endif
    %endfor
    % if not value.get("matches_remote", True):
        <div class="tree-button">
            <input type="submit" class="button-warning" value="Clean" name="clean_resource">
        </div>
        <p class="tree-item-message">
            <img title="This resource is absent from the remote server." class="icon-warning"
                 src="${request.static_url('magpie.ui.home:static/exclamation-triangle.png')}" alt="WARNING" />
        </p>
    % endif
    % if level == 0:
        <div class="tree-button">
            <input type="submit" class="tree-button goto-service theme" value="Edit Service" name="goto_service">
        </div>
    % endif
</%def>


<%block name="breadcrumb">
<li><a href="${request.route_url('home')}">
    Home</a></li>
<li><a href="${request.route_url('view_users')}">
    Users</a></li>
<li><a href="${request.route_url('edit_user', user_name=user_name, cur_svc_type=cur_svc_type)}">
    User [${user_name}]</a></li>
</%block>

<h1>Edit User: [${user_name}]</h1>

<h3>User Information</h3>


<div class="panel-box">
    <div class="panel-heading theme">
        <form id="delete_user" action="${request.path}" method="post">
            <span class="panel-title">User: </span>
            <span class="panel-value">[${user_name}]</span>
            <span class="panel-heading-button">
                <input type="submit" value="Delete" name="delete" class="button delete">
            </span>
        </form>
    </div>
    <div class="panel-body">
        <div class="panel-box">
            <div class="panel-heading subsection">
                <div class="panel-title">Details</div>
            </div>
            <div>
                <form id="edit_username" action="${request.path}" method="post">
                    <p class="panel-line">
                        <span class="panel-entry">Username: </span>
                        %if edit_mode == 'edit_username':
                            <label>
                            <input type="text" value="${user_name}" name="new_user_name"
                                   id="input_username" onkeyup="adjustWidth('input_name')">
                            <input type="submit" value="Save" name="save_username" class="button theme">
                            <input type="submit" value="Cancel" name="no_edit" class="button cancel">
                            </label>
                        %else:
                            <label>
                            <span class="panel-value">${user_name}</span>
                            <input type="submit" value="Edit" name="edit_username" class="button theme">
                            </label>
                        %endif
                    </p>
                </form>
                <form id="edit_password" action="${request.path}" method="post">
                    <p class="panel-line">
                        <span class="panel-entry">Password: </span>
                        %if edit_mode == "edit_password":
                            <label>
                            <input type="text" value="" name="new_user_password"
                                   id="input_password" onkeyup="adjustWidth('input_name')">
                            <input type="submit" value="Save" name="save_password" class="button theme">
                            <input type="submit" value="Cancel" name="no_edit" class="button cancel">
                            </label>
                        %else:
                            <label>
                            <span class="panel-value">***</span>
                            <input type="submit" value="Edit" name="edit_password" class="button theme">
                            </label>
                        %endif
                    </p>
                </form>
                <form id="edit_email" action="${request.path}" method="post">
                    <p class="panel-line">
                        <span class="panel-entry">Email: </span>
                        %if edit_mode == "edit_email":
                            <label>
                            <input type="text" value="${email}" name="new_user_email"
                                   id="input_email" onkeyup="adjustWidth('input_url')">
                            <input type="submit" value="Save" name="save_email" class="button theme">
                            <input type="submit" value="Cancel" name="no_edit" class="button cancel">
                            </label>
                        %else:
                            <label>
                            <span class="panel-value">${email}</span>
                            <input type="submit" value="Edit" name="edit_email" class="button theme">
                            </label>
                        %endif
                    </p>
                </form>
            </div>
        </div>
    </div>
</div>


<h3>Groups Membership</h3>

<form id="edit_membership" action="${request.path}" method="post">
    <input type="hidden" value="True" name="edit_group_membership"/>
    <table class="simple-list">
    %for group in groups:
    <tr>
        <td>
            <label>
            <input type="checkbox" value="${group}" name="member"
                %if group in own_groups:
                   checked
                %endif
                %if group in MAGPIE_FIXED_GROUP_MEMBERSHIPS:
                   disabled
                %else:
                   onchange="document.getElementById('edit_membership').submit()"
                %endif
               >
            ${group}
            </label>
        </td>
    </tr>
    %endfor
    </table>
</form>

<h3>Permissions</h3>

<form id="toggle_visible_perms" action="${request.path}" method="post">
    <label>
    <input type="checkbox" value="${inherit_groups_permissions}" name="toggle_inherit_groups_permissions"
           onchange="document.getElementById('toggle_visible_perms').submit()"
    %if inherit_groups_permissions:
        checked>
        <input type="hidden" value="False" name="inherit_groups_permissions"/>
    %else:
        >
        <input type="hidden" value="True" name="inherit_groups_permissions"/>
    %endif
    View inherited group permissions
    </label>
</form>

<div class="tabs-panel">

    %for svc_type in svc_types:
        % if cur_svc_type == svc_type:
            <a class="current-tab"
               href="${request.route_url('edit_user', user_name=user_name, cur_svc_type=svc_type)}">${svc_type}</a>
        % else:
            <a class="tab theme"
               href="${request.route_url('edit_user', user_name=user_name, cur_svc_type=svc_type)}">${svc_type}</a>
        % endif
    %endfor

    <div class="current-tab-panel">
        <div class="clear"></div>
        %if error_message:
            <div class="alert alert-danger alert-visible">${error_message}</div>
        %endif
        <form id="sync_info" action="${request.path}" method="post">
            <p class="panel-line">
                <span class="panel-entry">Last synchronization with remote services: </span>
                %if sync_implemented:
                    <span class="panel-value">${last_sync} </span>
                    <input type="submit" value="Sync now" name="force_sync" class="button-warning">
                %else:
                    <span class="panel-value">Not implemented for this service type.</span>
                %endif
            </p>
            %if ids_to_clean and not out_of_sync:
                <p class="panel-line">
                    <span class="panel-entry">Note: </span>
                    <span class="panel-value">Some resources are absent from the remote server </span>
                    <input type="hidden" value="${ids_to_clean}" name="ids_to_clean">
                    <input type="submit" class="button-warning" value="Clean all" name="clean_all">
                </p>
            %endif
        </form>
        <div class="tree-header">
        <div class="tree-item">Resources</div>
        %for perm in permissions:
            <div class="perm-title">${perm}</div>
        %endfor
        </div>
        <div class="tree">
            ${tree.render_tree(render_item, resources)}
        </div>
    </div>
</div>
