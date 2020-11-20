<%inherit file="magpie.ui.home:templates/template.mako"/>
<%inherit file="magpie.ui.management:templates/tree_scripts.mako"/>
<%namespace name="tree" file="magpie.ui.management:templates/tree_scripts.mako"/>

<%block name="breadcrumb">
<li><a href="${request.route_url('home')}">Home</a></li>
<li><a href="${request.route_url('view_users')}">Users</a></li>
<li>
    <a href="${request.route_url('edit_user', user_name=user_name, cur_svc_type=cur_svc_type)}">
    User [${user_name}]
    </a>
</li>
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
            <div class="panel-fields">
                <table class="panel-line">
                    <tr>
                        <td>
                            <span class="panel-entry">Username: </span>
                        </td>
                        <td>
                            <form id="edit_username" action="${request.path}" method="post">
                                <div class="panel-line-entry">
                                    %if edit_mode == "edit_username":
                                        <label>
                                        <input type="text" placeholder="new user name" name="new_user_name"
                                               id="input_username" value="${user_name}"
                                               onkeyup="adjustWidth('input_username')">
                                        <input type="submit" value="Save" name="save_username" class="button theme">
                                        <input type="submit" value="Cancel" name="no_edit" class="button cancel">
                                        </label>
                                    %else:
                                        <label>
                                        <span class="panel-line-textbox">${user_name}</span>
                                        <input type="submit" value="Edit" name="edit_username" class="button theme">
                                        </label>
                                    %endif
                                </div>
                            </form>
                        </td>
                        <td>
                        %if invalid_user_name:
                            <div class="panel-form-error">
                                <img src="${request.static_url('magpie.ui.home:static/exclamation-circle.png')}"
                                     alt="ERROR" class="icon-error" />
                                <div class="alert-form-text">
                                    ${reason_user_name}
                                </div>
                            </div>
                        %endif
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <span class="panel-entry">Password: </span>
                        </td>
                        <td>
                            <form id="edit_password" action="${request.path}" method="post">
                                <div class="panel-line-entry">
                                    %if edit_mode == "edit_password":
                                        <label>
                                        <input type="password" placeholder="new password" name="new_user_password"
                                               id="input_password" value=""
                                               onkeyup="adjustWidth('input_password')">
                                        <input type="submit" value="Save" name="save_password" class="button theme">
                                        <input type="submit" value="Cancel" name="no_edit" class="button cancel">
                                        </label>
                                    %else:
                                        <label>
                                        <span class="panel-value">***</span>
                                        <input type="submit" value="Edit" name="edit_password" class="button theme">
                                        </label>
                                    %endif
                                </div>
                            </form>
                        </td>
                        <td>
                        %if invalid_password:
                            <div class="panel-form-error">
                                <img src="${request.static_url('magpie.ui.home:static/exclamation-circle.png')}"
                                     alt="ERROR" class="icon-error" />
                                <div class="alert-form-text">
                                    ${reason_password}
                                </div>
                            </div>
                        %endif
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <span class="panel-entry">Email: </span>
                        </td>
                        <td>
                            <form id="edit_email" action="${request.path}" method="post">
                                <div class="panel-line-entry">
                                    %if edit_mode == "edit_email":
                                        <label>
                                        <input type="email" placeholder="new email" name="new_user_email"
                                               id="input_email" value="${email}"
                                               onkeyup="adjustWidth('input_url')">
                                        <input type="submit" value="Save" name="save_email" class="button theme">
                                        <input type="submit" value="Cancel" name="no_edit" class="button cancel">
                                        </label>
                                    %else:
                                        <label>
                                        <span class="panel-value">${email}</span>
                                        <input type="submit" value="Edit" name="edit_email" class="button theme">
                                        </label>
                                    %endif
                                </div>
                            </form>
                        </td>
                        <td>
                        %if invalid_user_email:
                            <div class="panel-form-error">
                                <img src="${request.static_url('magpie.ui.home:static/exclamation-circle.png')}"
                                     alt="ERROR" class="icon-error" />
                                <div class="alert-form-text">
                                    ${reason_user_email}
                                </div>
                            </div>
                        %endif
                        </td>
                    </tr>
                </table>
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
            <label class="checkbox-align">
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

<div class="option-container">
    <div class="option-section">
        <form id="toggle_visible_perms" action="${request.path}" method="post">
            <label class="checkbox-align">
            <input type="checkbox" value="${inherit_groups_permissions}" name="toggle_inherit_groups_permissions"
                   onchange="document.getElementById('toggle_visible_perms').submit()"
            %if inherit_groups_permissions:
                checked>
                <input type="hidden" value="False" name="inherit_groups_permissions"/>
            %else:
                >
                <input type="hidden" value="True" name="inherit_groups_permissions"/>
            %endif
            <span class="option-text">
            View inherited group permissions and effective user permissions.
            </span>
            </label>
        </form>
    </div>
    %if inherit_groups_permissions:
    <div class="clear"></div>
    <div class="option-section">
        <div class="alert-note alert-visible">
            <img src="${request.static_url('magpie.ui.home:static/info.png')}"
                 alt="INFO" class="icon-info alert-info" title="User effective permission resolution." />
            <meta name="source" content="https://commons.wikimedia.org/wiki/File:Infobox_info_icon.svg">
            <div class="alert-note-text">
                <p>
                    Individual resources can be tested for effective access using the
                    <input type="button" value="?" class="permission-effective-button button-no-click">
                    <span>button next to the corresponding permission.</span>
                    <br>Displayed permissions combine user direct permissions and inherited group permissions.
                </p>
            </div>
        </div>
    </div>
    <div class="clear"></div>
    <div class="option-section">
        <div class="alert-note alert-visible">
            <img src="${request.static_url('magpie.ui.home:static/exclamation-triangle.png')}"
                 alt="WARNING" class="icon-warning" title="Administrators effective permission resolution." />
            <div class="alert-note-text">
                <p>
                    Users member of the administrative group have full effective access regardless of permissions.
                </p>
            </div>
        </div>
    </div>
    %endif
</div>
<div class="clear"></div>

<div class="tabs-panel">
    <div class="tab-panel-selector">
        %for svc_type in svc_types:
            % if cur_svc_type == svc_type:
                <a class="tab current-tab"
                   href="${request.route_url('edit_user', user_name=user_name, cur_svc_type=svc_type)}">${svc_type}</a>
            % else:
                <a class="tab theme"
                   href="${request.route_url('edit_user', user_name=user_name, cur_svc_type=svc_type)}">${svc_type}</a>
            % endif
        %endfor
    </div>

    <div class="current-tab-panel">
        <div class="clear underline"></div>
        %if error_message:
            <div class="alert alert-danger alert-visible">${error_message}</div>
        %endif

        ${tree.sync_resources()}
        ${tree.render_resource_permission_tree(resources, permissions)}
    </div>
</div>
