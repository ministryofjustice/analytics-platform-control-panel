/**
 * Add Another module
 *
 * Wrapper around the MOJ Frontend Add Another component.
 * Initializes any elements with data-module="moj-add-another" attribute.
 *
 * @see https://design-patterns.service.justice.gov.uk/components/add-another/
 */

moj.Modules.addAnother = {
  selector: '[data-module="moj-add-another"]',

  init() {
    const $elements = document.querySelectorAll(this.selector);
    if ($elements.length === 0) {
      return;
    }

    $elements.forEach(($element) => {
      this.initComponent($element);
    });
  },

  /**
   * Initialize add another component on an element
   * @param {HTMLElement} $root - The root element with data-module="moj-add-another"
   */
  initComponent($root) {
    $root.addEventListener('click', (event) => this.onAddButtonClick(event, $root));
    $root.addEventListener('click', (event) => this.onRemoveButtonClick(event, $root));

    // Ensure buttons are type="button" to prevent form submission
    const $buttons = $root.querySelectorAll('.moj-add-another__add-button, .moj-add-another__remove-button');
    $buttons.forEach(($button) => {
      if ($button instanceof HTMLButtonElement) {
        $button.type = 'button';
      }
    });
  },

  /**
   * Handle add button click
   * @param {MouseEvent} event
   * @param {HTMLElement} $root
   */
  onAddButtonClick(event, $root) {
    const $button = event.target;
    if (!($button instanceof HTMLButtonElement) || !$button.classList.contains('moj-add-another__add-button')) {
      return;
    }

    const $items = this.getItems($root);
    const $newItem = this.getNewItem($root);
    if (!$newItem) {
      return;
    }

    this.updateAttributes($newItem, $items.length);
    this.resetItem($newItem);

    // Add remove button to first item if it doesn't have one
    const $firstItem = $items[0];
    if (!this.hasRemoveButton($firstItem)) {
      this.createRemoveButton($firstItem);
    }

    // Insert new item after the last one
    $items[$items.length - 1].after($newItem);

    // Focus the first input in the new item
    const $input = $newItem.querySelector('input, textarea, select');
    if ($input) {
      $input.focus();
    }
  },

  /**
   * Handle remove button click
   * @param {MouseEvent} event
   * @param {HTMLElement} $root
   */
  onRemoveButtonClick(event, $root) {
    const $button = event.target;
    if (!($button instanceof HTMLButtonElement) || !$button.classList.contains('moj-add-another__remove-button')) {
      return;
    }

    const $item = $button.closest('.moj-add-another__item');
    if ($item) {
      $item.remove();
    }

    const $items = this.getItems($root);

    // Remove the remove button if only one item left
    if ($items.length === 1) {
      const $removeBtn = $items[0].querySelector('.moj-add-another__remove-button');
      if ($removeBtn) {
        $removeBtn.remove();
      }
    }

    // Re-index all items
    $items.forEach(($item, index) => {
      this.updateAttributes($item, index);
    });

    // Focus the heading
    this.focusHeading($root);
  },

  /**
   * Get all items in the add another component
   * @param {HTMLElement} $root
   * @returns {HTMLElement[]}
   */
  getItems($root) {
    return Array.from($root.querySelectorAll('.moj-add-another__item'));
  },

  /**
   * Check if an item has a remove button
   * @param {HTMLElement} $item
   * @returns {boolean}
   */
  hasRemoveButton($item) {
    return $item.querySelectorAll('.moj-add-another__remove-button').length > 0;
  },

  /**
   * Clone the first item to create a new one
   * @param {HTMLElement} $root
   * @returns {HTMLElement|null}
   */
  getNewItem($root) {
    const $items = this.getItems($root);
    if ($items.length === 0) {
      return null;
    }

    const $item = $items[0].cloneNode(true);
    if (!($item instanceof HTMLElement)) {
      return null;
    }

    if (!this.hasRemoveButton($item)) {
      this.createRemoveButton($item);
    }

    return $item;
  },

  /**
   * Update data attributes on inputs to reflect their index
   * @param {HTMLElement} $item
   * @param {number} index
   */
  updateAttributes($item, index) {
    $item.querySelectorAll('[data-name]').forEach(($input) => {
      if (!this.isValidInputElement($input)) {
        return;
      }

      const name = $input.getAttribute('data-name') || '';
      const id = $input.getAttribute('data-id') || '';
      const originalId = $input.id;

      $input.name = name.replace(/%index%/g, `${index}`);
      $input.id = id.replace(/%index%/g, `${index}`);

      // Update associated label
      const $label = $input.parentElement.querySelector('label') ||
                     $input.closest('label') ||
                     $item.querySelector(`[for="${originalId}"]`);

      if ($label && $label instanceof HTMLLabelElement) {
        $label.htmlFor = $input.id;
      }
    });
  },

  /**
   * Create a remove button and append it to the item
   * @param {HTMLElement} $item
   */
  createRemoveButton($item) {
    const $button = document.createElement('button');
    $button.type = 'button';
    $button.classList.add('govuk-button', 'govuk-button--secondary', 'moj-add-another__remove-button');
    $button.textContent = 'Remove';
    $item.append($button);
  },

  /**
   * Reset all inputs in an item to their default values
   * @param {HTMLElement} $item
   */
  resetItem($item) {
    $item.querySelectorAll('[data-name], [data-id]').forEach(($input) => {
      if (!this.isValidInputElement($input)) {
        return;
      }

      if ($input instanceof HTMLSelectElement) {
        $input.selectedIndex = 0;
        $input.value = '';
      } else if ($input instanceof HTMLTextAreaElement) {
        $input.value = '';
      } else if ($input instanceof HTMLInputElement) {
        switch ($input.type) {
          case 'checkbox':
          case 'radio':
            $input.checked = false;
            break;
          default:
            $input.value = '';
        }
      }
    });

    // Clear any error states
    $item.querySelectorAll('.govuk-form-group--error').forEach(($group) => {
      $group.classList.remove('govuk-form-group--error');
    });
    $item.querySelectorAll('.govuk-error-message').forEach(($error) => {
      $error.remove();
    });
    $item.querySelectorAll('.govuk-input--error, .govuk-select--error, .govuk-textarea--error').forEach(($input) => {
      $input.classList.remove('govuk-input--error', 'govuk-select--error', 'govuk-textarea--error');
    });
  },

  /**
   * Focus the heading element for accessibility
   * @param {HTMLElement} $root
   */
  focusHeading($root) {
    const $heading = $root.querySelector('.moj-add-another__heading');
    if ($heading instanceof HTMLElement) {
      $heading.focus();
    }
  },

  /**
   * Check if an element is a valid form input
   * @param {Element} $input
   * @returns {boolean}
   */
  isValidInputElement($input) {
    return $input instanceof HTMLInputElement ||
           $input instanceof HTMLSelectElement ||
           $input instanceof HTMLTextAreaElement;
  }
};
