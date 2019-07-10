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
    if (document.querySelectorAll(this.formClass).length) {
      this.selectField = document.getElementById(this.selectId);
      this.roleListEndpoint = this.selectField.dataset.roleEndpoint;
      this.getRoles().then(() => {
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
    return fetch(this.roleListEndpoint, {
      method: "GET"
    }).then(response => response.json()).then(data => {
      this.roles = data;
    })
  },

  loadRolesToSelect() {
    const appTypeRadio = document.querySelector('input[name=app_type]:checked')
    const appType = appTypeRadio ? appTypeRadio.value : null;
    let roles = this.roles || [];
    if (roles && appType) {
      roles = this.roles.filter(name => this.roleFilters[appType].test(name));
    }
    this.selectField.querySelectorAll('option:not([value=""])').forEach(option => option.remove());
    this.selectField.id = this.id;
    document.querySelector(this.autocompleteWrapperClass).remove();
    accessibleAutocomplete.enhanceSelectElement({
      id: this.id,
      selectElement: document.querySelector('#' + this.id),
      source: roles
    });
    roles.forEach(role => {
      this.selectField.options[this.selectField.options.length] = new Option(role, role);
    });
  }
};
