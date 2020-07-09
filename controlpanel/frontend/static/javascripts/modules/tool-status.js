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

    // Bind version selects' change event listeners
    const versionSelects = document.querySelectorAll(this.versionSelector);
    versionSelects.forEach(versionSelect => {
      versionSelect.addEventListener("change", (event) => this.versionSelectChanged(event.target));
    });
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
    const selectElement = listener.querySelector(this.versionSelector);

    if (newVersion) {
      // 1. remove "(not installed)" option
      let notInstalledOption = selectElement.querySelector("option." + this.versionNotInstalledClass);

      if (notInstalledOption) {
        notInstalledOption.remove();
      }

      // 2. remove "(installed)" suffix and class from old version
      let oldVersionOption = selectElement.querySelector("option." + this.versionInstalledClass);

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

    // After deploy, update select/deploy button
    this.versionSelectChanged(selectElement);
  },

  showActions(listener, action_names) {
    listener.querySelectorAll(this.actionClass).forEach(action => {
      action.classList.toggle(this.hidden, !action_names.includes(action.dataset.actionName));
    });
  },

  // version select "change" event handler
  versionSelectChanged(target) {
    const selected = target.options[target.options.selectedIndex];
    const classes = selected.className.split(" ");

    const notInstalledSelected = classes.indexOf(this.versionNotInstalledClass) !== -1;
    const installedSelected = classes.indexOf(this.versionInstalledClass) !== -1;

    const deployButton = target.closest(`form${this.actionClass}[data-action-name='deploy']`).querySelector("button");

    // If "(not installed)" or "(installed)" version selected
    // the "Deploy" button needs to be disabled
    deployButton.disabled = notInstalledSelected || installedSelected;
  },
};
