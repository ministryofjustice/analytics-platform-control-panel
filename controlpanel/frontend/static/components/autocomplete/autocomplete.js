moj.Modules.autocomplete = {
  selector: ".autocomplete-select",

  init() {
    if (document.querySelector(this.selector)) {
      this.bindEvents();
    }
  },

  bindEvents() {
    document.querySelectorAll(this.selector).forEach(select => {
      accessibleAutocomplete.enhanceSelectElement({
        selectElement: select,
      });
    });
  },
};
