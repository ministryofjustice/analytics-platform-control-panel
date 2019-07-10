moj.Modules.roleNames = {
  id: "role_name",
  selectId: "role_name-select",
  selectSelector: "#role_name-select",
  roleEndpointAttr: "data-role-endpoint",
  formClass: ".appRoles",
  autocompleteWrapperClass: ".autocomplete__wrapper",
  roleFilters: {
    airflow: new RegExp('^airflow_'),
    webapp: new RegExp('^(alpha|dev)_app_'),
  },
  roles: null,

  init() {
    this.$selectField = $(this.selectSelector);
    this.roleListEndpoint = this.$selectField.attr(this.roleEndpointAttr);
    if (document.querySelectorAll(this.formClass).length) {
      this.getRoles().done(() => {
        this.loadRolesToSelect();
        this.bindEvents();
      });
    }
  },

  bindEvents() {
    document.querySelectorAll('input[name=app_type]').forEach(input => {
      input.addEventListener('change', (event) => {
        this.loadRolesToSelect();
      });
    });
  },

  getRoles() {
    return $.get(
      this.roleListEndpoint,
      (data) => {
        this.roles = data;
      }
    )
  },

  loadRolesToSelect() {
    const appType = $('input[name=app_type]:checked').val();
    let roles = this.roles || [];
    if (roles && appType) {
      roles = this.roles.filter(name => this.roleFilters[appType].test(name));
    }
    this.$selectField.find('option:not([value=""])').remove();
    this.$selectField.attr('id', this.id);
    $(this.autocompleteWrapperClass).remove();
    accessibleAutocomplete.enhanceSelectElement({
      id: this.id,
      selectElement: document.querySelector('#' + this.id),
      source: roles
    });
    const select = document.getElementById(this.selectId);
    roles.forEach(role => {
      select.options[select.options.length] = new Option(role, role);
    });
  }
};
