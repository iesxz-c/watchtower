(function (global, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    global.WatchTower = factory();
  }
})(typeof window !== "undefined" ? window : this, function () {
  let config = {
    endpoint: "",
    apiKey: "",
    appId: "",
    environment: "production",
    release: "1.0.0",
    sampleRate: 1.0,
    captureConsoleErrors: false
  };

  let eventQueue = [];
  let timerId = null;

  function init(options) {
    config = { ...config, ...options };
    setupGlobalHandlers();
    startBatchTimer();
  }

  function captureError(err) {
    try {
      if (Math.random() > config.sampleRate) return;
      eventQueue.push({
        app_id: config.appId,
        environment: config.environment,
        release_version: config.release,
        url: window.location.href,
        user_agent: navigator.userAgent,
        error_type: err.name || "Error",
        message: err.message || String(err),
        stack: err.stack || "",
        timestamp: new Date().toISOString()
      });
      checkQueueSize();
    } catch (e) {}
  }

  function captureMessage(msg, level = "error") {
    try {
      if (Math.random() > config.sampleRate) return;
      eventQueue.push({
        app_id: config.appId,
        environment: config.environment,
        release_version: config.release,
        url: window.location.href,
        user_agent: navigator.userAgent,
        error_type: "Message",
        message: `[${level}] ${msg}`,
        timestamp: new Date().toISOString()
      });
      checkQueueSize();
    } catch (e) {}
  }

  function flush() {
    if (eventQueue.length === 0) return;
    const batch = [...eventQueue];
    eventQueue = [];

    batch.forEach(event => {
      fetch(config.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-WatchTower-Key": config.apiKey
        },
        body: JSON.stringify(event)
      }).catch(() => {});
    });
  }

  function checkQueueSize() {
    if (eventQueue.length >= 10) {
      flush();
    }
  }

  function startBatchTimer() {
    if (timerId) clearInterval(timerId);
    timerId = setInterval(flush, 5000);
  }

  function setupGlobalHandlers() {
    const originalOnError = window.onerror;
    window.onerror = function (msg, url, line, col, error) {
      if (error) {
        captureError(error);
      } else {
        captureMessage(`${msg} at ${url}:${line}:${col}`);
      }
      if (originalOnError) return originalOnError.apply(this, arguments);
      return false;
    };

    const originalOnUnhandledRejection = window.onunhandledrejection;
    window.onunhandledrejection = function (event) {
      if (event.reason instanceof Error) {
        captureError(event.reason);
      } else {
        captureMessage(String(event.reason), "UnhandledRejection");
      }
      if (originalOnUnhandledRejection) return originalOnUnhandledRejection.apply(this, arguments);
      return false;
    };

    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
      try {
        const response = await originalFetch.apply(this, args);
        if (!response.ok) {
          eventQueue.push({
            app_id: config.appId,
            environment: config.environment,
            release_version: config.release,
            url: window.location.href,
            user_agent: navigator.userAgent,
            error_type: "FetchError",
            message: `Fetch failed with status: ${response.status}`,
            api_context: { endpoint: typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : "unknown"), status: response.status },
            timestamp: new Date().toISOString()
          });
          checkQueueSize();
        }
        return response;
      } catch (err) {
        captureError(err);
        throw err;
      }
    };
  }

  return { init, captureError, captureMessage, flush };
});
