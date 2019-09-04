moj.Modules.tool_deploy = {
  class: ".tool-deploy-form",

  init() {
    if (document.querySelector(this.class)) {
      this.bindEvents();
    }
  },

  bindEvents() {
    document.querySelectorAll(this.class).forEach(form => {
      form.addEventListener('submit', e => {
        e.preventDefault();
        e.stopPropagation();
        $.post(form.getAttribute('action'), $(form).serialize());
      });
    });
  }
};
