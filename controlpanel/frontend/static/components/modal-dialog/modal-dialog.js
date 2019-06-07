moj.Modules.modals = {
  triggerClass: '.modal-dialog--trigger',

  init() {
    const triggers = document.querySelectorAll(this.triggerClass);
    if (triggers.length) {
      this.bindEvents();
    }
  },

  bindEvents() {
    document.querySelectorAll(this.triggerClass).forEach(trigger => {
      trigger.addEventListener("click", event => {
        const dialog = document.getElementById(trigger.dataset.dialogId);
        dialog.showModal();
      });
    });
  },
};
