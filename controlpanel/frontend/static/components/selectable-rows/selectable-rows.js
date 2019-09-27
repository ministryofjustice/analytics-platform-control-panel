/**
 * Module to allow selecting entire rows in a table instead of using a small checkbox.
 *
 * It will disable any in-row actions buttons once a selection is made, but will re-enable them once
 * all the selections are cleared.
 *
 * It can optionally support enabling a (global)
 * button(s) that lives outside the table.
 * How to use:
 *  1. Add the class "selectable-rows" to your <table>
 *  2. For any button you want to enable when there are selections add the class "selectable-rows__enable-on-selections"
 *  3. Use the macro `row_selector` to put insert an invisible input box in the first column of your table
 * The module will automatically disable any action buttons that are in side the row.
 *
 * WARNING: This module doesn't support more than 1 table on the same page
 * @type {{init(): void, onSelectionChanged(*): void, baseClass: string, bindEvents(): void}}
 */

moj.Modules.selectable_rows = {
  baseClass: "selectable-rows",

  init() {
    this.tableRowSelector = `.${this.baseClass} tr`;
    this.tableRowButtonSelector = `${this.tableRowSelector} button`;
    this.selectionClass = `${this.baseClass}__row-selected`;
    this.enableOnSelectionSelector = `.${this.baseClass}__enable-on-selections`;
    this.selectionChangedEventName = `${this.baseClass}:rowSelectionChanged`;
    if (document.querySelector(this.tableRowSelector)) {
      this.bindEvents();
    }
  },

  /**
   * Runs when rows are selected/deselected
   * @param event
   */
  onSelectionChanged(event) {
    const rowButtons = document.querySelectorAll(this.tableRowButtonSelector);
    const enableOnSelectionButtons = document.querySelectorAll(
      this.enableOnSelectionSelector
    );
    if (event.detail.rowsSelected.length > 0) {
      // some rows are selected
      rowButtons.forEach(e => (e.disabled = true));
      enableOnSelectionButtons.forEach(e => e.disabled = false);
    } else {
      rowButtons.forEach(e => (e.disabled = false));
      enableOnSelectionButtons.forEach(e => e.disabled = true);
    }
  },

  bindEvents() {
    window.addEventListener(this.selectionChangedEventName, e =>
      this.onSelectionChanged(e)
    );
    document.querySelectorAll(this.tableRowSelector).forEach(row => {
      row.addEventListener("click", event => {
        const checkbox = row.querySelector(
          "input[type='checkbox'].row-selector"
        );

        // user clicks on the button, don't select the row
        if (event.target.tagName === "BUTTON") {
          return true;
        }
        if (checkbox) {
          // user clicks somewhere on the row that isn't the checkbox itself
          if (event.target !== checkbox) {
            checkbox.checked = !checkbox.checked;
          }
          // make row state match state of checkbox
          if (checkbox.checked) {
            row.classList.add(this.selectionClass);
          } else {
            row.classList.remove(this.selectionClass);
          }

          const rowSelectionChangedEvent = new CustomEvent(
            this.selectionChangedEventName,
            {
              bubbles: true,
              detail: {
                rowsSelected: row
                  .closest("table")
                  .querySelectorAll(`tr.${this.selectionClass}`)
              }
            }
          );
          event.target.dispatchEvent(rowSelectionChangedEvent);
        }
      });
    });
  }
};
