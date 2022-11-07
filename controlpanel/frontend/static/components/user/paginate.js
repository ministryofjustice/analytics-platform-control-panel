var app_customers = [];
var search_tag = "#list-users-paginated";
var display_tag = "#list-customers-paginated";
var checkbox_controller_row = "#checkbox-controller"

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
        <input type="checkbox" class="row-selector customer-checkbox" name="customer" value="${ user_id }" autocomplete="off">
      </td>
      <td class="govuk-table__cell">${ email }</td>
      ${delete_customer}
    </tr>`
}

function disableMore() {
  $("#add_more").prop('disabled', true);
}

function enableMore() {
  $("#add_more").prop('disabled', false);
}

function loadCustomers(app_pk, index, perm) {
  $("#loading_gif").show();
  disableMore();
  let url = `/api/cpanel/v1/app/${app_pk}/customers/${index}/`;

  fetch(url)
  .then(response => response.json())
  .then(data => {
    let new_entries = data.users.map(item => getCustomerEntry(item.user_id, item.email, perm))
    app_customers = app_customers.concat(new_entries);

    $('#repos_loaded').text(app_customers.length);

    // $(search_tag).autocomplete('option', 'source', app_customers);
    $(display_tag).append(new_entries);

    $("#loading_gif").hide();
    $("#loading_text").text("loaded: ");

    $('#current_index').val(index +1);
    $('#total_available').html(`/${ data.total }`);

    if(app_customers.length >= parseInt(data.total)){
      disableMore();
    }
    else {
      enableMore();
    }
  })
  .catch((err) => {
    let error_msg = "Error. contact the AP team if this error persists.";
    let content = `<span><span class="ui-icon ui-icon-alert"></span> ${error_msg}</span>`;
    $('#list-users-paginated').html(content);
  });
}

function toggleRemoveAll() {
  let submit = $('.selectable-rows__enable-on-selections');
  let disabled = ""
  if ($('.customer-checkbox:checked').length == 0) {
    disabled = "disabled";
  }
  submit.prop("disabled", disabled);
}

function toggleSelected() {
  let element = $(`${checkbox_controller_row}>td>input`);
  let new_value = element.prop('checked');
  $('.customer-checkbox').prop('checked', new_value);
  toggleRemoveAll();
}

moj.Modules.paginate = {
  selector: search_tag,
  has_remove_client_perm: false,
  bindEvents() {
    // toggle checkboxes feature - start
    $(`#toggle-controller`).on('click', function() {
      $(this).prop("checked", !$(this).prop("checked"));
      toggleSelected();
    });

    $(document).on('click', '.customer-checkbox', () => toggleRemoveAll());

    $(`${checkbox_controller_row}`).on('click', function(){
      let checkBox = $(`${checkbox_controller_row}>td>input`);
      checkBox.prop("checked", !checkBox.prop("checked"));
      toggleSelected()
    })
    // end

    // vars
    const perm = $('#has_remove_client_perm').val();
    const app_pk = $('#app_id').val();
    let index = parseInt($('#current_index').val());

    loadCustomers(app_pk, index, perm);
    $('#ui-id-1').css({'padding-inline-start': '0px'});

    $('#add_more').on('click', function() {
      let index = parseInt($('#current_index').val());
      loadCustomers(app_pk, index, perm);
      $('#ui-id-1').css({'padding-inline-start': '0px'});
    });
  },
  init() {
    if($(display_tag).length){
      this.bindEvents();
    }
  }
}
