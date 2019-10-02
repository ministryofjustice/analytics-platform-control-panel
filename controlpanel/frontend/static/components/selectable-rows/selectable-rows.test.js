const simulant = require('jsdom-simulant');
require('./selectable-rows');

describe('selectable-rows', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = `
      <html lang="en">
      <body>
      <form action="#" onsubmit="return false">
        <button id="outsideButton" class="selectable-rows__enable-on-selections" disabled="disabled" type="submit" name="submit">do something</button>
        <table class="selectable-rows">
          <thead>
          <tr>
            <th></th>
            <th>Customer</th>
            <th>Actions</th>
          </tr>
          </thead>
          <tbody>
          <tr id="row1">
            <td>
              <input type="checkbox" class="row-selector" name="customer" value="email|1234" autocomplete="off">
            </td>
            <td>fake@fake</td>
            <td>
              <button class="rowButton" name="customer" value="email|1234">
                Remove customer
              </button>
            </td>
          </tr>
          <tr id="row2">
            <td>
              <input type="checkbox" class="row-selector" name="customer" value="email|5678" autocomplete="off">
            </td>
            <td>fake@fake</td>
            <td>
              <button class="rowButton" name="customer" value="email|5678">
                Remove customer
              </button>
            </td>
          </tr>
          </tbody>
        </table>
      </form>
      </body>
      </html>
    `;
  });
  describe('init()', () => {
    test('that bindEvents is called in init - if selector present', () => {
      const spy = jest.spyOn(moj.Modules.selectable_rows, 'bindEvents');
      moj.Modules.selectable_rows.init();
      expect(spy).toHaveBeenCalled();
    });
    test('that bindEvents is not called - if selector not present', () => {
      document.documentElement.innerHTML = `<html lang="en">`;
      const spy = jest.spyOn(moj.Modules.selectable_rows, 'bindEvents');
      moj.Modules.selectable_rows.init();
      expect(spy).not.toHaveBeenCalled();
    });
    test('selectors are initialised', () => {
      moj.Modules.selectable_rows.init();
      expect(moj.Modules.selectable_rows.tableRowSelector).not.toBeUndefined();
      expect(moj.Modules.selectable_rows.tableRowButtonSelector).not.toBeUndefined();
      expect(moj.Modules.selectable_rows.selectionClass).not.toBeUndefined();
      expect(moj.Modules.selectable_rows.enableOnSelectionSelector).not.toBeUndefined();
      expect(moj.Modules.selectable_rows.selectionChangedEventName).not.toBeUndefined();
    });
  });
  describe("events", () => {
    beforeEach(() => {
      moj.Modules.selectable_rows.init();
    });

    test("click on row selects the checkbox on the row", () => {
      const rowElem = document.getElementById('row1');
      const checkbox = rowElem.querySelector('input.row-selector');
      expect(checkbox.checked).toBe(false);
      simulant.fire(rowElem, 'click');
      expect(checkbox.checked).toBe(true);
    });
    test("click on row twice leaves the row deselected", () => {
      const rowElem = document.getElementById('row1');
      const checkbox = rowElem.querySelector('input.row-selector');
      expect(checkbox.checked).toBe(false);
      simulant.fire(rowElem, 'click');
      expect(checkbox.checked).toBe(true);
      simulant.fire(rowElem, 'click');
      expect(checkbox.checked).toBe(false);
    });
    test("click on row enables 'enable-on-selections' button", () => {
      const rowElem = document.getElementById('row1');
      const mutliActionButton = document.getElementById('outsideButton');
      expect(mutliActionButton).toBeDisabled();
      simulant.fire(rowElem, 'click');
      expect(mutliActionButton).not.toBeDisabled();
    });
    test("click on row disables row action button", () => {
      const rowElem = document.getElementById('row1');
      const rowButtons = document.querySelectorAll('.rowButton');
      rowButtons.forEach(elem => expect(elem).not.toBeDisabled());
      simulant.fire(rowElem, 'click');
      rowButtons.forEach(elem => expect(elem).toBeDisabled());
    });
    test("click on row button doesn't select row", () => {
      const rowElem = document.getElementById('row1');
      const rowButton = rowElem.querySelector('.rowButton');
      const checkbox = rowElem.querySelector('input.row-selector');

      expect(checkbox.checked).toBe(false);

      simulant.fire(rowButton, 'click');

      expect(checkbox.checked).toBe(false);
    });
  });
});
