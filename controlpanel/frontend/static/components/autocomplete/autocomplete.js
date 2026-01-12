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
        defaultValue: '',
        selectElement: select,
        required: select.dataset.required === "true",
        showAllValues: select.dataset.showAllValues === "true",
        autoselect: false,
        dropdownArrow: () => '<svg class="autocomplete__dropdown-arrow-down" style="top: 8px;" viewBox="0 0 10 6"><polyline points="1 1 5 5 9 1" stroke="currentColor" stroke-width="1" fill="none"></polyline></svg>'
      });
    });
  },
};
