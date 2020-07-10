moj.Modules.jsConfirm = {
  confirmClass: 'js-confirm',
  defaultConfirmMessage: 'Are you sure?',

  init() {
    this.bindEvents();
  },

  bindEvents() {
    $(document).on('click', `a.${this.confirmClass}`, (e) => {
      const $el = $(e.target);
      e.preventDefault();

      if (window.confirm(this.getConfirmMessage($el))) {
        window.document.location = $el.attr('href');
      }
    });

    // works on any children of a `<form>` with `confirmClass` but it's
    // usually used on `<input type="submit">` or `<button>`
    $(document).on('click', `form .${this.confirmClass}`, (e) => {
      const $el = $(e.target);
      e.preventDefault();

      if (window.confirm(this.getConfirmMessage($el))) {
        $el.closest('form').submit();
      }
    });
  },

  getConfirmMessage($el) {
    return $el.data('confirm-message') || this.defaultConfirmMessage;
  },
};
