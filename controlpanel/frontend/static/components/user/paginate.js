
class CustomerUi {
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

  loadedCount(count) {
    $('#customers_loaded').text(count);
  }

  showLoadingGif() {
    $("#loading_gif").show();
  }

  hideLoadingGif() {
    $("#loading_gif").hide();
  }
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
    this.ui = ui;
    this.perm = $('#has_remove_client_perm').val()
    this.app_customers = [];

    this.display_tag = "#list-customers-paginated";
    this.processDataFunc = this.processData.bind(this);
  }

  processData(data) {
    let new_entries = data.results.map(item => getCustomerEntry(item.user_id, item.email, this.perm))
    this.app_customers = this.app_customers.concat(new_entries);

    this.ui.loadedCount(this.app_customers.length);
    $(this.display_tag).append(new_entries);

    this.ui.updateCount(data.count);
    this.next_url = data.links.next;

    (!data.links.next)?this.ui.disableMore():this.ui.enableMore();
  }

  responseError(err) {
    console.log('err >>> ', err, '<<<');
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

function getCustomerEntry(user_id, email, delete_perm) {
  let delete_customer = '';

  if(delete_perm) {
    delete_customer = `<td class="govuk-table__cell">
      <button class="govuk-button govuk-button--secondary right"
            name="customer"
            value="${user_id}">
        Remove customer
      </button>
    </td>`
  }

  return `<tr class="govuk-table__row">
      <td class="govuk-table__cell checkbox-cell">
        <input type="checkbox" class="row-selector customer-checkbox" name="customer" value="${user_id}" autocomplete="off" />
      </td>
      <td class="govuk-table__cell">${email}</td>
      ${delete_customer}
    </tr>`
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
    let ui = new CustomerUi();
    let paginate = new PaginateRequest(`/api/cpanel/v1/app/${app_pk}/customers/paginate/`, ui);

    $('#ui-id-1').css({'padding-inline-start': '0px'});
    paginate.getNextPage();
    $('#add_more').on('click', () => paginate.getNextPage());
  },
  init() {
    if($("#list-customers-paginated").length){
      this.bindEvents();
    }
  }
}
