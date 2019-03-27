moj.Modules.accessPanels = {
  buttonClass: 'js-change-access-level',
  panelClass: 'change-data-access-level-panel',

  init() {
    if ($(`.${this.buttonClass}`).length) {
      this.bindEvents();
    }
  },

  bindEvents() {
    $(`.${this.buttonClass}`).on('click', (e) => {
      this.closeOpenPanels();
      this.togglePanel($(e.target).siblings('.panel'));
    });
    $('.js-close-panel').on('click', (e) => {
      this.togglePanel($(e.target).closest('.panel'));
    });
  },

  togglePanel($panel) {
    $panel.toggleClass('js-hidden');
    $panel.siblings(`.${this.buttonClass}`).toggle();
  },

  closeOpenPanels() {
    $(`.${this.panelClass}:not(.js-hidden)`).each((n, panel) => {
      this.togglePanel($(panel));
    });
  },
};
