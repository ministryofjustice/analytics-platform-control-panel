moj.Modules.secretsForm = {
  selectID: "secret_key",
  formElementClass: "hide-forms",
  formsectionClass: "form-section",

  init() {
    if ($(`#${this.selectID}`).length) {
      this.bindEvents();
    }
  },

  updateForm() {
    // select: onchange
    // - find the select-value
    // - hide all form
    // - find form with the select-value
    // - unhide parent section

    $(`.${this.formsectionClass}`).addClass(`${this.formElementClass}`);
    let value = $(`#${this.selectID}`).find(':selected').val();
    let elementInput = $(`input[value='${ value }'][name='secret_key']`);
    elementInput.parent().parent().removeClass(`${this.formElementClass}`);
  },
  
  bindEvents() {
    let updateForm = this.updateForm.bind(this);
    $(`#${this.selectID}`).on('change', updateForm);
  }
};
  