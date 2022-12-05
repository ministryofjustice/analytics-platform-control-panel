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
        // higher priority: Check if the button has API URL for submit
        const target_url = $el.data("form-url");
        // Check if the button has a target form to submit.
        const target = $el.data("form-target");
        if(target_url) {
            $.ajax({
                type: "POST",
                url: target_url,
                data: $('#' + target).serializeArray(),
                success: function () {
                    console.log('success post');
                }
            });
        } else if (target) {
            document.getElementById(target).submit();
        } else
        {
            // If not, just submit the closest form.
            $el.closest('form').submit();
        }
      }
    });
  },

  getConfirmMessage($el) {
    return $el.data('confirm-message') || this.defaultConfirmMessage;
  },
};
