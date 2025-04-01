import mixpanel from 'mixpanel-browser';

const MIXPANEL_TOKEN = import.meta.env.VITE_MIXPANEL_TOKEN;

mixpanel.init(MIXPANEL_TOKEN);

const mixpanelService = {
  track: (eventName, properties) => {
    mixpanel.track(eventName, properties);
  },
  identify: (userId) => {
    mixpanel.identify(userId);
  },
  setProfile: (properties) => {
    mixpanel.people.set(properties);
  },
};

const mixpanelPlugin = {
  install: (app) => {
    // Make it available via provide/inject system
    app.provide('mixpanel', mixpanelService);
  },
};

export default mixpanelPlugin;
