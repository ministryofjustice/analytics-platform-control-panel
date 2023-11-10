moj.Modules.trackAppTask = {
  eventType: "taskStatus",
  listenerClass: ".track_task",
  alertsClass: ".alerts",
  mojPrimaryNavigationClass: ".moj-primary-navigation",

  init() {
    const taskStatusListeners = document.querySelectorAll(this.listenerClass);
    if (taskStatusListeners) {
      this.bindEvents(taskStatusListeners);
    }
  },

  bindEvents(listeners) {
    listeners.forEach(listener => {
      moj.Modules.eventStream.addEventListener(
        this.eventType,
        this.buildEventHandler(listener)
      );
    });
  },

  buildEventHandler(listener) {
    const appTask = this;
    return event => {
      const data = JSON.parse(event.data);
      switch (data.status.toUpperCase()) {
        case 'COMPLETED':
          appTask.updateMessage("The " + data.entity_name + "'s task (" + data.task_description + ") has been completed")
          break;
      };
    };
  },

  updateMessage(newMessage) {
    // 2. Added new message
    let elementLocation = document.querySelector(this.mojPrimaryNavigationClass);
    if (elementLocation) {
      var AlertsElement = document.querySelector(this.alertsClass);
      if (!AlertsElement) {
        AlertsElement = document.createElement("div");
        AlertsElement.setAttribute("class", 'alerts govuk-width-container');
        elementLocation.after(AlertsElement);
      };

      var newMessageTagElement = document.createElement("div");
      newMessageTagElement.setAttribute("class", 'alerts--item success');
      var newMessageElement = document.createElement("span");
      newMessageElement.setAttribute("class", 'alerts--message');
      newMessageElement.innerHTML = newMessage;

      newMessageTagElement.appendChild(newMessageElement);
      AlertsElement.appendChild(newMessageTagElement);
//      elementLocation.after(AlertsElement);
    }
  }

};
