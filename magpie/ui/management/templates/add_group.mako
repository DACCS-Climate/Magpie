<%inherit file="magpie.ui.home:templates/template.mako"/>

<%block name="breadcrumb">
<li><a href="${request.route_url('home')}">Home</a></li>
<li><a href="${request.route_url('view_groups')}">Groups</a></li>
<li><a href="${request.route_url('add_group')}">Add Group</a></li>
</%block>

<h1>Add Group</h1>

<form class="new-item-form" id="add_group_form" action="${request.path}" method="post">
    <input type="hidden" value="${request.route_url('home')}" name="came_from">
    <table class="fields-table">
        <tr>
            <td>Group name:</td>
            <td>
                <label>
                    <input type="text" name="group_name" value="${form_group_name}" />
                </label>
            </td>
            <td>
                <div class="alert-form-error"
                    %if not invalid_group_name:
                        style="visibility: hidden"
                    %endif
                >
                    <img src="${request.static_url('magpie.ui.home:static/exclamation-circle.png')}"
                             alt="ERROR" class="icon-error" />
                    <div class="alert-form-text">
                        ${reason_group_name}
                    </div>
                </div>
            </td>
        </tr>
        <tr>
            <td>Description:</td>
            <td>
                <label>
                    <input type="text" name="description" value="${form_description}" />
                </label>
            </td>
            <td>
                %if not invalid_description:
                (optional)
                %else:
                <div class="alert-form-error"
                    %if not invalid_description:
                        style="visibility: hidden"
                    %endif
                >
                    <img src="${request.static_url('magpie.ui.home:static/exclamation-circle.png')}"
                             alt="ERROR" class="icon-error" />
                    <div class="alert-form-text">
                        ${reason_description}
                    </div>
                </div>
                %endif
            </td>
        </tr>
        <tr>
            <td>Discoverable:</td>
            <td>
                <label>
                    <input type="checkbox" name="discoverable" id="input_discoverable"
                    %if form_discoverable:
                        checked
                    %endif
                    >
                </label>
            </td>
            <td>
            </td>
        </tr>
        <tr>
            <td class="centered" colspan="2">
                <input type="submit" value="Add Group" name="create" class="button theme">
            </td>
        </tr>
    </table>
</form>
