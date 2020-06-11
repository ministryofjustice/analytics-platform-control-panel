moj.Modules.toolStatus = {
  actionClass: ".tool-action",
  eventType: "toolStatus",
  hidden: "govuk-visually-hidden",
  listenerClass: ".tool-status",
  statusLabelClass: ".tool-status-label",
  toolAppVersionClass: ".tool-app-version",

  init() {
    const toolStatusListeners = document.querySelectorAll(this.listenerClass);
    if (toolStatusListeners) {
      this.bindEvents(toolStatusListeners);
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
    return event => {
      const data = JSON.parse(event.data);
      if (data.toolName != listener.dataset.toolName) {
        return;
      }
      listener.querySelector(this.statusLabelClass).innerText = data.status;
      switch (data.status.toUpperCase()) {
        case 'NOT DEPLOYED':
          this.showActions(listener, ['deploy']);
          break;
        case 'DEPLOYING':
          this.showActions(listener, []);
          // maybe have a Cancel button? Report issue?
          break;
        case 'READY':
        case 'IDLED':
          this.showActions(listener, ['open', 'restart', 'upgrade', 'remove']);
          this.updateAppVersion(listener, data.appVersion);
          break;
        case 'UPGRADED':
          this.showActions(listener, ['open']);
          this.updateAppVersion(listener, data.appVersion);
          break;
        case 'FAILED':
          this.showActions(listener, ['restart', 'upgrade', 'remove']);
          break;
      }
    };
  },

  updateAppVersion(listener, newAppVersion) {
    if (newAppVersion) {
      listener.querySelector(this.toolAppVersionClass).innerText = newAppVersion;
    }
  },

  showActions(listener, action_names) {
    listener.querySelectorAll(this.actionClass).forEach(action => {
      action.classList.toggle(this.hidden, !action_names.includes(action.dataset.actionName));
    });
  }
};
