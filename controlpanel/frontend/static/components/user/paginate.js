// class Customer {
//   user_id: String = ""
//   email: String = ""
// }

// const CustomerList {
//   customers: Customer
// }


class CustomerUi {
  constructor(delete_perm) {
    this.delete_perm = delete_perm;
    this.display_tag = "#list-customers-paginated";
    this.data = {customers: []};
  }

  disableMore() {
    $("#add_more").prop('disabled', true);
  }

  enableMore() {
    $("#add_more").prop('disabled', false);
  }

  updateCount(count) {
    $("#loading_text").text("loaded: ");
    $('#total_available').html(`/${ count }`);
  }

  loadedCount() {
    $('#customers_loaded').text(this.data.customers.length);
  }

  showLoadingGif() {
    $("#loading_gif").show();
  }

  hideLoadingGif() {
    $("#loading_gif").hide();
  }

  updateRows() {
    let rows = this.data.customers || [];
    let items = rows.map(item => this.getCustomerEntry(item.user_id, item.email));

    $(this.display_tag).empty();
    $(this.display_tag).append(items);
    this.loadedCount();
  }

  getCustomerEntry(user_id, email) {
    let delete_customer = '';
  
    if(this.delete_perm) {
      delete_customer = `<td class="govuk-table__cell">
        <button class="govuk-button govuk-button--secondary right"
              name="customer"
              value="${user_id}">
          Remove customer
        </button>
      </td>`
    }
  
    return `<tr class="govuk-table__row result_rows" data-user="${ email }" >
        <td class="govuk-table__cell checkbox-cell">
          <input type="checkbox" class="row-selector customer-checkbox" name="customer" value="${user_id}" autocomplete="off" />
        </td>
        <td class="govuk-table__cell">${email}</td>
        ${delete_customer}
      </tr>`
  }

  getData() {
    return this.data;
  }

  hideAll() {
    $('.result_rows').hide();
  }

  showAll() {
    $('.result_rows').show();
  }

  showRows(customer_data) {
    // customer_data: "Customer"
    let entries = $('.result_rows');
    let customer_emails = customer_data.map(item => item.email);

    entries.each( (index, element) => {
      if (customer_emails.includes($(element).data("user") )) {
        $(element).show();
      }
    });
  }
}

const CustomerSearchable = function(ui) {
  let searchTag = '#customer-search-box';
  $(searchTag).on('keyup', function() {
    let value = $(this).val();
    if (value.length < 3) {
      ui.showAll();
      return
    }

    let data = ui.getData();
    let items = data.customers;
    let found_items = items.filter( item => item.email.indexOf(value.toLowerCase()) > -1 );

    ui.hideAll();
    ui.showRows(found_items);
  });
}

class CustomerSelectable {
  constructor(checkbox_controller_row) {
    this.checkbox_cntl = checkbox_controller_row;
  }

  toggleRemoveAll() {
    let submit = $('.selectable-rows__enable-on-selections');
    let disabled = ""
    if ($('.customer-checkbox:checked').length == 0) {
      disabled = "disabled";
    }
    submit.prop("disabled", disabled);
  }
  
  toggleSelected() {
    let element = $(`${this.checkbox_cntl}>td>input`);
    let new_value = element.prop('checked');
    $('.customer-checkbox').prop('checked', new_value);
    this.toggleRemoveAll();
  }
}

class PaginateRequest {
  constructor(url, ui) {
    this.next_url = url;
    // this.group_id = group_id;
    this.ui = ui;
    this.app_customers = {customers: []};
    this.ui.data = this.app_customers;
    this.processDataFunc = this.processData.bind(this);
  }

  processData(data) {
    // let new_entries = data.results.map(item => getCustomerEntry(item.user_id, item.email, this.perm))
    let new_entries = data.results.map(item => ({"user_id": item.user_id, "email": item.email}));
    this.app_customers.customers = this.app_customers.customers.concat(new_entries);
    this.ui.updateRows();

    this.ui.updateCount(data.count);
    this.next_url = data.links.next;
    (!data.links.next)?this.ui.disableMore():this.ui.enableMore();
  }

  responseError(err) {
    console.log(err);
    let error_msg = "Error. contact the AP team if this error persists.";
    let content = `<span><span class="ui-icon ui-icon-alert"></span> ${error_msg}</span>`;
    $('#list-users-paginated').html(content);
  }

  getNextPage() {
    this.ui.showLoadingGif();

    fetch(this.next_url)
      .then(response => {
        this.ui.hideLoadingGif();
        return response.json();
      })
      .then(this.processDataFunc)
      .catch(this.responseError);
  }
}

const fetchGroupId = (app_id) => {
  let url = `/api/cpanel/v1/app/${ app_id }/group_id/`
  return fetch(url)
    .then(response => response.json())
    .then(result => result.group_id)
    .catch('failed to get group_id')
}

moj.Modules.paginate = {
  bindEvents() {
    let selected = new CustomerSelectable("#checkbox-controller");

    // toggle checkboxes feature - start
    $(`#toggle-controller`).on('click', function() {
      $(this).prop("checked", !$(this).prop("checked"));
      selected.toggleSelected();
    });

    $(document).on('click', '.customer-checkbox', () => selected.toggleRemoveAll());

    $(`${selected.checkbox_cntl}`).on('click', function(){
      let checkBox = $(`${selected.checkbox_cntl}>td>input`);
      checkBox.prop("checked", !checkBox.prop("checked"));
      selected.toggleSelected();
    })
    // end

    const app_pk = $('#app_id').val();
    let group_id = fetchGroupId(app_pk);

    group_id.then( group_id => {
      let perm = $('#has_remove_client_perm').val()
      let ui = new CustomerUi(perm);
      CustomerSearchable(ui);
      let paginate = new PaginateRequest(`/api/cpanel/v1/app/${app_pk}/customers/paginate/?${ new URLSearchParams({"group_id": group_id }) }`, ui);
  
      $('#ui-id-1').css({'padding-inline-start': '0px'});
      paginate.getNextPage();
      $('#add_more').on('click', () => paginate.getNextPage());
    });
  },
  init() {
    if($("#list-customers-paginated").length){
      this.bindEvents();
    }
  }
}
