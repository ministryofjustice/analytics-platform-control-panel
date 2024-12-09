moj.Modules.toolStatus = {
  actionClass: ".tool-action",
  buttonClass: ".govuk-button",
  eventType: "toolStatus",
  hidden: "govuk-visually-hidden",
  listenerClass: ".tool",
  statusLabelClass: ".tool-status-label",

  versionSelector: "select[name='version']",
  versionNotInstalledClass: "not-installed",
  versionInstalledClass: "installed",
  installedSuffix: " (installed)",
  alertsClass: ".alerts",
  mojPrimaryNavigationClass: ".moj-primary-navigation",

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
    const toolstatus = this;
    return event => {
      const data = JSON.parse(event.data);
      if (data.toolName.startsWith(listener.dataset.toolName) === false ) {
        return;
      }
      listener.querySelector(toolstatus.statusLabelClass).innerText = data.status;
      switch (data.status.toUpperCase()) {
        case 'NOT DEPLOYED':
          toolstatus.showActions(listener, ['deploy']);
          break;
        case 'DEPLOYING':
          toolstatus.showActions(listener, []);
          toolstatus.updateMessage("Deploying " + data.toolName + "... this may take several minutes")
          // maybe have a Cancel button? Report issue?
          break;
        case 'READY':
          toolstatus.showActions(listener, ['open', 'restart']);
          toolstatus.updateAppVersion(listener, data);
          toolstatus.updateMessage("The tool has been deployed")
          break;
        case 'IDLED':
          toolstatus.showActions(listener, ['deploy', 'open', 'restart', 'remove']);
          toolstatus.updateAppVersion(listener, data);
          break;
        case 'FAILED':
          toolstatus.showActions(listener, ['deploy', 'restart', 'remove']);
          break;
      }
    };
  },

  // Select the new version from the tool "version" select input
  updateAppVersion(listener, newVersionData) {
    const selectElement = listener.querySelector(this.versionSelector);

    if (newVersionData) {
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
      let newValue = newVersionData.toolName + "__" + newVersionData.version + "__" + newVersionData.tool_id;
      let newVersionOption = listener.querySelector(this.versionSelector + " option[value='" + newValue + "']");
      if (newVersionOption) {
        newVersionOption.innerText = newVersionOption.innerText + this.installedSuffix;
        newVersionOption.classList.add(this.versionInstalledClass)

        // set the new version as the current chosen item
        const dropDownToolId = "tools-" + listener.dataset.toolName;
        document.getElementById(dropDownToolId).selectedIndex = newVersionOption.index;
      }
    }

    // After deploy, update select/deploy button
    this.versionSelectChanged(selectElement);
  },

  updateMessage(newMessage) {
    // 1. Remove the old messages
    let existingAlerts = document.querySelector(this.alertsClass);
    if (existingAlerts) {
      existingAlerts.remove();
    };

    // 2. Added new message
    let elementLocation = document.querySelector(this.mojPrimaryNavigationClass);
    if (elementLocation) {
      var newAlertsElement = document.createElement("div");
      newAlertsElement.setAttribute("class", 'alerts govuk-width-container');
      var newMessageTagElement = document.createElement("div");
      newMessageTagElement.setAttribute("class", 'alerts--item success');
      var newMessageElement = document.createElement("span");
      newMessageElement.setAttribute("class", 'alerts--message');
      newMessageElement.innerHTML = newMessage;

      newMessageTagElement.appendChild(newMessageElement);
      newAlertsElement.appendChild(newMessageTagElement);
      elementLocation.after(newAlertsElement);
    }
  },

  showActions(listener, actionNames) {
    listener.querySelectorAll(this.actionClass).forEach(action => {
      const actionName = action.dataset.actionName;
      const button = listener.querySelector(`${this.buttonClass}[data-action-name='${actionName}']`);

      if (actionNames.includes(actionName)) {
        button.removeAttribute("disabled");
      } else {
        button.setAttribute("disabled", true);
      }
    });
  },

  // version select "change" event handler
  versionSelectChanged(target) {
    const selected = target.options[target.options.selectedIndex];
    const classes = selected.className.split(" ");

    const notInstalledSelected = classes.indexOf(this.versionNotInstalledClass) !== -1;
    const installedSelected = classes.indexOf(this.versionInstalledClass) !== -1;

    const targetTool = target.attributes["data-action-target"];
    const deployButton = document.getElementById("deploy-" + targetTool.value);

    // If "(not installed)" or "(installed)" version selected
    // the "Deploy" button needs to be disabled
    deployButton.disabled = notInstalledSelected || installedSelected;

    this.toggleDeprecationMessage(selected, targetTool);
  },

  toggleDeprecationMessage(selected, targetTool) {
    const isDeprecated = selected.attributes["data-is-deprecated"].value === "True";
    const deprecationMessageElement = document.getElementById(targetTool.value + "-deprecation-message");
    const deprecationMessage = selected.attributes["data-deprecated-message"].value;

    if (isDeprecated) {
      deprecationMessageElement.firstChild.innerText = deprecationMessage;
      deprecationMessageElement.classList.remove(this.hidden);
    } else {
      deprecationMessageElement.classList.add(this.hidden);
      deprecationMessageElement.firstChild.innerText = "";
    }
  }
};
