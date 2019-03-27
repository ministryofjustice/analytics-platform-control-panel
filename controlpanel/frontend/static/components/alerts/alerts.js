moj.Modules.alerts = {
  alertsClass: 'alerts',

  init() {
    this.bindEvents();
  },

  bindEvents() {
    $(document).on('click', `.${this.messageClass}`, (e) => {
      $(e.target).fadeOut();
    });
  },
};
