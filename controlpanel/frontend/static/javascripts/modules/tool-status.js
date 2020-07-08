moj.Modules.toolStatus = {
  actionClass: ".tool-action",
  eventType: "toolStatus",
  hidden: "govuk-visually-hidden",
  listenerClass: ".tool",
  statusLabelClass: ".tool-status-label",

  versionSelector: "select[name='version']",
  versionNotInstalledClass: "not-installed",
  versionInstalledClass: "installed",
  installedSuffix: " (installed)",

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
          this.showActions(listener, ['deploy', 'open', 'restart', 'remove']);
          this.updateAppVersion(listener, data.version);
          break;
        case 'FAILED':
          this.showActions(listener, ['deploy', 'restart', 'remove']);
          break;
      }
    };
  },

  // Select the new version from the tool "version" select input
  updateAppVersion(listener, newVersion) {
    if (newVersion) {
      // 1. remove "(not installed)" option
      let notInstalledOption = listener.querySelector(this.versionSelector + " ." + this.versionNotInstalledClass);

      if (notInstalledOption) {
        notInstalledOption.remove();
      }

      // 2. remove "(installed)" suffix and class from old version
      let oldVersionOption = listener.querySelector(this.versionSelector + " ." + this.versionInstalledClass);

      if (oldVersionOption) {
        oldVersionOption.innerText = oldVersionOption.innerText.replace(this.installedSuffix, "");
        oldVersionOption.classList.remove(this.versionInstalledClass);
      }

      // 3. add "(installed)" suffix and class to new version
      let newVersionOption = listener.querySelector(this.versionSelector + " option[value='" + newVersion + "']");

      if (newVersionOption) {
        newVersionOption.innerText = newVersionOption.innerText + this.installedSuffix;
        newVersionOption.classList.add(this.versionInstalledClass)
      }
    }
  },

  showActions(listener, action_names) {
    listener.querySelectorAll(this.actionClass).forEach(action => {
      action.classList.toggle(this.hidden, !action_names.includes(action.dataset.actionName));
    });
  }
};
