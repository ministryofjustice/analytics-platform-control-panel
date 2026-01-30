moj.Modules.autocomplete = {
  selector: ".autocomplete-select",

  init() {
    if (document.querySelector(this.selector)) {
      this.bindEvents();
      this.initAddAnother();
    }
  },

  enhanceSelect(select) {
    accessibleAutocomplete.enhanceSelectElement({
      defaultValue: '',
      selectElement: select,
      required: select.dataset.required === "true",
      showAllValues: select.dataset.showAllValues === "true",
      autoselect: false,
      dropdownArrow: () => '<svg class="autocomplete__dropdown-arrow-down" style="top: 8px;" viewBox="0 0 10 6"><polyline points="1 1 5 5 9 1" stroke="currentColor" stroke-width="1" fill="none"></polyline></svg>',
      // Custom onConfirm to fix the bug where clearing the input doesn't clear the hidden select.
      // By default, accessible-autocomplete only updates the select when a valid option is selected,
      // leaving the previously selected value when the input is cleared.
      // See: https://github.com/alphagov/accessible-autocomplete/issues/205
      onConfirm: (query) => {
        // The library calls onConfirm in two scenarios:
        // 1. User clicks an option: query = the option's text (e.g., "Bar Chart 2")
        // 2. User blurs the field: query = undefined (library's internal state resets after selection)
        //
        // Since we can't rely on query being set on blur, we read the visible input's
        // current value as the source of truth for what should be selected.
        const inputId = select.id.replace('-select', '');
        const input = document.getElementById(inputId);
        const valueToMatch = query || (input ? input.value.trim() : '');

        // Try to find a matching option
        const matchingOption = valueToMatch ? Array.from(select.options).find(
          option => option.textContent === valueToMatch
        ) : null;

        if (matchingOption) {
          matchingOption.selected = true;
        } else {
          // No match - reset to empty option
          // This handles: empty input, partial text, or gibberish
          select.selectedIndex = 0;
        }
      }
    });
  },

  bindEvents() {
    document.querySelectorAll(this.selector).forEach(select => {
      this.enhanceSelect(select);
    });
  },

  // Re-initialize autocomplete when moj-add-another clones an item.
  // Cloned items have stale autocomplete wrappers that need replacing.
  initAddAnother() {
    const addAnotherContainers = document.querySelectorAll('[data-module="moj-add-another"]');

    addAnotherContainers.forEach(container => {
      if (!container.querySelector(this.selector)) return;

      const addButton = container.querySelector('.moj-add-another__add-button');
      if (!addButton) return;

      addButton.addEventListener('click', () => {
        // Let moj-add-another finish cloning before we clean up
        setTimeout(() => {
          const items = container.querySelectorAll('.moj-add-another__item');
          const newItem = items[items.length - 1];
          if (!newItem) return;

          const select = newItem.querySelector(this.selector);
          if (!select) return;

          // Remove cloned autocomplete wrapper (has stale IDs)
          const wrapper = newItem.querySelector('.autocomplete__wrapper');
          if (wrapper && wrapper.parentNode) {
            wrapper.parentNode.remove();
          }

          // Re-initialize
          select.style.display = '';
          this.enhanceSelect(select);
        }, 0);
      });
    });
  },
};
