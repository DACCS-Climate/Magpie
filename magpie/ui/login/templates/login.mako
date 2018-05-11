<%inherit file="ui.home:templates/template.mako"/>

<%block name="breadcrumb">
<li><a href="${request.route_url('home')}">Home</a></li>
<li><a href="${request.route_url('login')}">Log in</a></li>
</%block>

<h1>Log in</h1>

<form class="new_item_form" action="${request.route_url('login')}" method="post">
    <h3>Magpie</h3>
    <input type="hidden" value="${request.route_url('home')}" name="came_from" id="came_from">
    <input type="hidden" value="ziggurat" name="provider_name">
    <table class="fields_table">
        <tr>
            <td>Username:</td>
            <div class="input_container">
                <td><input type="text" name="user_name" value="${user_name}" class="equal_width"></td>
            </div>
            %if invalid_username:
                <td><p class="alert_form_error">
                    <img src="${request.static_url('ui.home:static/warning_exclamation.png')}" /> unknown username </p>
                </td>
            %endif
        </tr>
        <tr>
            <td>Password:</td>
            <div class="input_container">
                <td><input type="password" name="password" value="" class="equal_width"></td>
            </div>
            %if invalid_password:
                <td><p class="alert_form_error">
                    <img src="${request.static_url('ui.home:static/warning_exclamation.png')}" /> incorrect password </p>
                </td>
            %endif
        </tr>
        <tr><td class="centered" colspan="2"><input type="submit" value="Sign In" name="submit" id="submit"></td></tr>
    </table>
</form>


<form class="new_item_form" action="" method="post">
    <h3>External SignIn</h3>
    <input type="hidden" value="${request.route_url('home')}" name="came_from">
    <table class="fields_table">
        <tr>
            <td>Username:</td>
            <div class="input_container">
                <td><input type="text" name="user_name" class="equal_width"></td>
            </div>
        </tr>
        <tr>
            <td>Provider:</td>
            <div class="input_container">
                <td><select name="provider_name" class="equal_width">
                    %for provider in external_providers:
                        <option value="${provider}">${provider}</option>
                    %endfor
                </select></td>
            </div>
        </tr>
        <tr><td class="centered" colspan="2"><input type="submit" value="Sign In" name="submit"></td></tr>
    </table>
</form>



